"""Seeds demo chats with ratings so the Chat Insights pages (usage, ratings,
history, export) have data without an LLM provider.

Run inside the api_server container:
    python -m onyx.db.seeding.chat_insights_demo            # seed
    python -m onyx.db.seeding.chat_insights_demo --purge    # remove demo data
"""

import argparse
import random
import secrets
from datetime import datetime, timedelta, timezone

from fastapi_users.password import PasswordHelper
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from onyx.configs.constants import MessageType
from onyx.db.chat import (
    create_chat_session,
    create_new_chat_message,
    get_or_create_root_message,
)
from onyx.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant
from onyx.db.models import ChatMessage, ChatMessageFeedback, ChatSession, Persona, User
from onyx.utils.logger import setup_logger

logger = setup_logger()

DEMO_PREFIX = "[demo] "
DEMO_USER_EMAILS = [
    "anna.wisniewska@example.com",
    "piotr.zielinski@example.com",
    "katarzyna.wojcik@example.com",
    "tomasz.lewandowski@example.com",
]
DEMO_MODELS = ["gpt-5-mini", "claude-haiku-4-5"]
_USER_EMAIL = User.__table__.c.email
_USER_ID = User.__table__.c.id

# (question, answer, rating) — rating: True / False / None (not rated),
# plus an optional reason and comment for negative ratings.
DEMO_CONVERSATIONS: list[tuple[str, str, bool | None, str | None, str | None]] = [
    (
        "Ile dni urlopu przysługuje mi w tym roku?",
        "Przy stażu pracy powyżej 10 lat przysługuje 26 dni urlopu wypoczynkowego.",
        True,
        None,
        None,
    ),
    (
        "Jak zgłosić delegację krajową?",
        "Wypełnij wniosek w systemie HR i dołącz plan podróży. Akceptuje przełożony.",
        True,
        None,
        None,
    ),
    (
        "Jaki jest limit na zakup sprzętu IT bez przetargu?",
        "Limit wynosi 5 000 zł netto na jedno zamówienie.",
        False,
        "Outdated information",
        "Od lipca limit to 8 000 zł.",
    ),
    (
        "Podsumuj regulamin pracy zdalnej.",
        "Praca zdalna jest możliwa do 3 dni w tygodniu po uzgodnieniu z przełożonym.",
        True,
        None,
        None,
    ),
    (
        "Kto zatwierdza faktury powyżej 50 tys. zł?",
        "Faktury powyżej 50 tys. zł zatwierdza dyrektor finansowy.",
        None,
        None,
        None,
    ),
    (
        "Jak skonfigurować VPN na nowym laptopie?",
        "Zainstaluj klienta VPN z portalu IT i zaloguj się kontem firmowym.",
        False,
        "Not helpful",
        "Brakuje instrukcji dla macOS.",
    ),
    (
        "Gdzie znajdę wzór umowy NDA?",
        "Wzór umowy NDA jest w repozytorium Działu Prawnego, folder Wzory.",
        True,
        None,
        None,
    ),
    (
        "Jakie są godziny pracy biura w Krakowie?",
        "Biuro w Krakowie jest otwarte od 8:00 do 18:00.",
        False,
        "Inaccurate",
        None,
    ),
]


def _demo_users(db_session: Session) -> list[User]:
    helper = PasswordHelper()
    users: list[User] = []
    for email in DEMO_USER_EMAILS:
        user = db_session.scalar(select(User).where(_USER_EMAIL == email))
        if user is None:
            # Inactive with a random password: the account exists only so the
            # demo data has several authors.
            user = User(
                email=email,
                hashed_password=helper.hash(secrets.token_urlsafe(32)),
                is_active=False,
                is_verified=True,
            )
            db_session.add(user)
            db_session.flush()
        users.append(user)
    return users


def seed_demo_chats(num_sessions: int, days: int) -> int:
    rng = random.Random(42)
    now = datetime.now(tz=timezone.utc)
    with get_session_with_current_tenant() as db_session:
        # The first account to sign up becomes admin, so demo accounts must
        # never be the first ones.
        has_real_user = db_session.scalar(
            select(_USER_ID).where(_USER_EMAIL.not_in(DEMO_USER_EMAILS)).limit(1)
        )
        if has_real_user is None:
            raise SystemExit("Sign up in Onyx first, then seed the demo data.")
        users = _demo_users(db_session)
        persona_ids = list(
            db_session.scalars(
                select(Persona.id)
                .where(Persona.deleted.is_(False))
                .order_by(Persona.id)
                .limit(3)
            )
        )
        for index in range(num_sessions):
            question, answer, rating, reason, comment = rng.choice(DEMO_CONVERSATIONS)
            session = create_chat_session(
                db_session,
                f"{DEMO_PREFIX}{question}",
                rng.choice(users).id,
                rng.choice(persona_ids) if persona_ids else None,
            )
            started = now - timedelta(
                days=rng.randint(0, days - 1), minutes=rng.randint(0, 600)
            )
            session.time_created = started
            session.time_updated = started + timedelta(minutes=2)

            parent = get_or_create_root_message(session.id, db_session)
            user_message = create_new_chat_message(
                chat_session_id=session.id,
                parent_message=parent,
                message=question,
                token_count=len(question.split()),
                message_type=MessageType.USER,
                commit=False,
                db_session=db_session,
            )
            user_message.time_sent = started
            assistant_message = create_new_chat_message(
                chat_session_id=session.id,
                parent_message=user_message,
                message=answer,
                token_count=len(answer.split()),
                message_type=MessageType.ASSISTANT,
                commit=False,
                db_session=db_session,
            )
            assistant_message.time_sent = started + timedelta(seconds=5)
            assistant_message.model_display_name = DEMO_MODELS[index % 2]

            if rating is not None:
                db_session.add(
                    ChatMessageFeedback(
                        chat_message_id=assistant_message.id,
                        is_positive=rating,
                        feedback_text=comment,
                        predefined_feedback=reason,
                    )
                )
        db_session.commit()
    logger.notice("Seeded %s demo chat sessions", num_sessions)
    return num_sessions


def purge_demo_chats() -> int:
    with get_session_with_current_tenant() as db_session:
        session_ids = list(
            db_session.scalars(
                select(ChatSession.id).where(
                    ChatSession.description.startswith(DEMO_PREFIX)
                )
            )
        )
        if session_ids:
            message_ids = select(ChatMessage.id).where(
                ChatMessage.chat_session_id.in_(session_ids)
            )
            db_session.execute(
                delete(ChatMessageFeedback).where(
                    ChatMessageFeedback.chat_message_id.in_(message_ids)
                )
            )
            # Break the message tree links before deleting the rows.
            db_session.query(ChatMessage).filter(
                ChatMessage.chat_session_id.in_(session_ids)
            ).update(
                {
                    ChatMessage.parent_message_id: None,
                    ChatMessage.latest_child_message_id: None,
                },
                synchronize_session=False,
            )
            db_session.execute(
                delete(ChatMessage).where(ChatMessage.chat_session_id.in_(session_ids))
            )
            db_session.execute(
                delete(ChatSession).where(ChatSession.id.in_(session_ids))
            )
        db_session.execute(delete(User).where(_USER_EMAIL.in_(DEMO_USER_EMAILS)))
        db_session.commit()
    logger.notice("Removed %s demo chat sessions", len(session_ids))
    return len(session_ids)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=120)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--purge", action="store_true")
    args = parser.parse_args()

    SqlEngine.init_engine(pool_size=5, max_overflow=0)
    if args.purge:
        purge_demo_chats()
    else:
        seed_demo_chats(args.sessions, max(args.days, 1))


if __name__ == "__main__":
    main()
