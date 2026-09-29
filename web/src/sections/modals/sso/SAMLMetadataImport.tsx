"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Button, InputTypeIn } from "@opal/components";
import { SvgSimpleLoader } from "@opal/icons";
import { InputVertical, Section, toast } from "@opal/layouts";
import { importSAMLMetadata } from "@/lib/sso/svc";
import type { SAMLIdPMetadata } from "@/lib/sso/interfaces";

interface SAMLMetadataImportProps {
  onImported: (metadata: SAMLIdPMetadata) => void;
}

/** Fills the IdP fields of a SAML provider from an IdP metadata URL, e.g.
 * Keycloak's /realms/<realm>/protocol/saml/descriptor. */
export default function SAMLMetadataImport({
  onImported,
}: SAMLMetadataImportProps) {
  const t = useTranslations("admin.ssoProviders.modals.provider.samlMetadata");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleImport() {
    setLoading(true);
    try {
      const metadata = await importSAMLMetadata({ metadata_url: url.trim() });
      onImported(metadata);
      toast.success(t("toasts.imported"));
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t("toasts.importFailed")
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <InputVertical title={t("title")} description={t("description")} withLabel>
      <Section
        flexDirection="row"
        alignItems="center"
        justifyContent="start"
        gap={0.5}
      >
        <InputTypeIn
          value={url}
          placeholder={t("placeholder")}
          aria-label={t("title")}
          onChange={(event) => setUrl(event.target.value)}
        />
        <Button
          type="button"
          prominence="secondary"
          disabled={loading || !url.trim()}
          icon={loading ? SvgSimpleLoader : undefined}
          onClick={() => void handleImport()}
        >
          {t("button")}
        </Button>
      </Section>
    </InputVertical>
  );
}
