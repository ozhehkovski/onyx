import { render, screen } from "@tests/setup/test-utils";
import { Table, createTableColumns } from "@opal/components";

interface Row {
  id: string;
  name: string;
}

const tc = createTableColumns<Row>();
const columns = [
  tc.column("name", {
    header: "Name",
    weight: 100,
    cell: (name) => <span>{name}</span>,
  }),
];
const rows: Row[] = Array.from({ length: 12 }, (_, i) => ({
  id: String(i),
  name: `row-${i}`,
}));

describe("Table pagination", () => {
  it("renders every row when pageSize is Infinity", () => {
    render(
      <Table
        data={rows}
        columns={columns}
        getRowId={(row) => row.id}
        pageSize={Infinity}
        emptyState={<span>empty</span>}
      />
    );
    expect(screen.queryByText("empty")).not.toBeInTheDocument();
    expect(screen.getByText("row-0")).toBeInTheDocument();
    expect(screen.getByText("row-11")).toBeInTheDocument();
  });

  it("still paginates with a finite pageSize", () => {
    render(
      <Table
        data={rows}
        columns={columns}
        getRowId={(row) => row.id}
        pageSize={5}
      />
    );
    expect(screen.getByText("row-4")).toBeInTheDocument();
    expect(screen.queryByText("row-5")).not.toBeInTheDocument();
  });
});
