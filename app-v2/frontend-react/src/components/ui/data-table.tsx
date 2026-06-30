import type { ColumnDef } from "@tanstack/react-table";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "#/lib/utils";

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
  classNameWrapper?: React.ComponentProps<'div'>['className'];
  classNameTable?: React.ComponentProps<'table'>['className'];
  classNameTHead?: React.ComponentProps<'thead'>['className'];
  classNameTHeadTr?: React.ComponentProps<'tr'>['className'];
  classNameTHeadTh?: React.ComponentProps<'th'>['className'];
  classNameTBody?: React.ComponentProps<'tbody'>['className'];
  classNameTBodyTr?: React.ComponentProps<'tr'>['className'];
  classNameTBodyTd?: React.ComponentProps<'td'>['className'];
}

export function DataTable<TData, TValue>({
  columns,
  data,
  classNameWrapper,
  classNameTable,
  classNameTHead,
  classNameTHeadTr,
  classNameTHeadTh,
  classNameTBody,
  classNameTBodyTr,
  classNameTBodyTd,
}: DataTableProps<TData, TValue>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className={cn("rounded-md border overflow-hidden", classNameWrapper)}>
      <Table className={classNameTable}>
        <TableHeader className={cn("", classNameTHead)}>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow
              key={headerGroup.id}
              className={classNameTHeadTr}
            >
              {headerGroup.headers.map((header) => {
                return (
                  <TableHead
                    key={header.id}
                    style={{
                      width: header.column.getSize(),
                      minWidth: header.column.columnDef.minSize,
                      maxWidth: header.column.columnDef.maxSize,
                    }}
                    className={classNameTHeadTh}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                  </TableHead>
                );
              })}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody className={classNameTBody}>
          {table.getRowModel().rows?.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                data-state={row.getIsSelected() && "selected"}
                className={classNameTBodyTr}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell
                    key={cell.id}
                    className={classNameTBodyTd}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={columns.length} className="h-24 text-center">
                No results.
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
