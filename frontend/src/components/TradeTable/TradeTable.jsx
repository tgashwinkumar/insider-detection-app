import { useState, useMemo } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table'
import TradeRow from '../TradeRow/TradeRow'
import WalletScorePanel from '../WalletScorePanel/WalletScorePanel'

const columnHelper = createColumnHelper()

// null scores sort below all real scores
function nullLastSortFn(rowA, rowB, columnId) {
  const a = rowA.getValue(columnId)
  const b = rowB.getValue(columnId)
  if (a === null && b === null) return 0
  if (a === null) return 1
  if (b === null) return -1
  return a < b ? -1 : a > b ? 1 : 0
}

const COLUMNS = [
  columnHelper.accessor('classification', { header: 'Classification', enableSorting: true }),
  columnHelper.accessor('wallet', { header: 'Wallet', enableSorting: false }),
  columnHelper.accessor('timestamp', { header: 'Time', enableSorting: true }),
  columnHelper.accessor('sizeUsdc', { header: 'Size (USDC)', enableSorting: true }),
  columnHelper.accessor('direction', { header: 'Direction', enableSorting: false }),
  columnHelper.accessor('insiderScore', {
    header: 'Score',
    enableSorting: true,
    sortingFn: nullLastSortFn,
  }),
  columnHelper.accessor('factors', { header: 'Factors', enableSorting: false }),
  columnHelper.display({ id: 'expand', header: '' }),
]

const FILTER_OPTIONS = ['all', 'insider', 'suspicious', 'clean']

export default function TradeTable({ trades, hasPendingScores }) {
  const [riskFilter, setRiskFilter] = useState('all')
  const [selectedTrade, setSelectedTrade] = useState(null)
  const [sorting, setSorting] = useState([{ id: 'insiderScore', desc: true }])

  const pendingCount = useMemo(
    () => trades.filter((t) => t.insiderScore === null).length,
    [trades]
  )

  const filtered = useMemo(
    () => (riskFilter === 'all' ? trades : trades.filter((t) => t.classification === riskFilter)),
    [trades, riskFilter]
  )

  const table = useReactTable({
    data: filtered,
    columns: COLUMNS,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  })

  const rows = table.getRowModel().rows

  return (
    <>
      <div className="bg-surface1 border border-border rounded overflow-hidden">
        {/* Filter tabs */}
        <div className="flex items-center gap-1 p-3 border-b border-border">
          <span className="text-muted text-xs font-data mr-2">Filter:</span>
          {FILTER_OPTIONS.map((f) => (
            <button
              key={f}
              onClick={() => setRiskFilter(f)}
              className={`px-3 py-1 rounded text-xs font-data capitalize transition-colors
                ${riskFilter === f
                  ? 'bg-surface2 text-white border border-border'
                  : 'text-muted hover:text-white'
                }`}
            >
              {f === 'all'
                ? `All (${trades.length})${pendingCount > 0 ? ` · ${pendingCount} pending` : ''}`
                : `${f} (${trades.filter((t) => t.classification === f).length})`}
            </button>
          ))}
          {hasPendingScores && (
            <span className="ml-auto flex items-center gap-1.5 text-muted text-xs font-data">
              <span className="w-1.5 h-1.5 rounded-full bg-suspicious animate-pulse" />
              scoring…
            </span>
          )}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                {table.getFlatHeaders().map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-2.5 text-left text-xs font-data font-semibold text-muted uppercase tracking-wider whitespace-nowrap"
                    onClick={header.column.getToggleSortingHandler()}
                    style={{ cursor: header.column.getCanSort() ? 'pointer' : 'default' }}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {header.column.getIsSorted() === 'asc' && ' ↑'}
                    {header.column.getIsSorted() === 'desc' && ' ↓'}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center text-muted py-10 text-sm font-data">
                    No trades match this filter.
                  </td>
                </tr>
              ) : (
                rows.map((row) => (
                  <TradeRow
                    key={row.original.id}
                    trade={row.original}
                    isSelected={selectedTrade?.id === row.original.id}
                    onClick={(t) => setSelectedTrade(selectedTrade?.id === t.id ? null : t)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-border">
          <span className="text-muted text-xs font-data">
            {filtered.length} trades · Page {table.getState().pagination.pageIndex + 1} of{' '}
            {table.getPageCount()}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
              className="px-2 py-1 text-xs font-data text-muted hover:text-white disabled:opacity-30 transition-colors"
            >
              ← Prev
            </button>
            <button
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
              className="px-2 py-1 text-xs font-data text-muted hover:text-white disabled:opacity-30 transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      </div>

      {/* Wallet panel */}
      {selectedTrade && (
        <WalletScorePanel trade={selectedTrade} onClose={() => setSelectedTrade(null)} />
      )}
    </>
  )
}
