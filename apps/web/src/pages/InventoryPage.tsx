import { useState, useMemo } from "react";
import {
  Search,
  Filter,
  Download,
  Check,
  Shield,
} from "lucide-react";
import type { InventoryRow } from "../types";
import { PanelHeader, StatusPill, csvCell } from "./shared";

interface InventoryPageProps {
  inventory: InventoryRow[];
}

export function InventoryPage({ inventory }: InventoryPageProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [storeFilter, setStoreFilter] = useState<"all" | "Store A" | "Store B">("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "quarantined" | "review" | "clear">("all");

  const filteredInventory = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return inventory.filter((row) => {
      if (storeFilter !== "all" && row.store !== storeFilter) return false;
      if (statusFilter !== "all" && row.status !== statusFilter) return false;
      if (!query) return true;
      return [row.store, row.sku, row.product, row.lot, row.location, row.status].some(
        (value) => value.toLowerCase().includes(query)
      );
    });
  }, [inventory, storeFilter, statusFilter, searchQuery]);

  const onHandTotal = filteredInventory.reduce((total, row) => total + row.onHand, 0);
  const quarantinedTotal = filteredInventory.reduce((total, row) => total + row.quarantined, 0);

  const exportInventoryCsv = () => {
    const header = ["Store", "SKU", "Product", "Lot", "On Hand", "Quarantined", "Confidence", "Status", "Location"];
    const rows = filteredInventory.map((row) => [
      row.store, row.sku, row.product, row.lot, String(row.onHand), String(row.quarantined),
      `${row.confidence}%`, row.status, row.location,
    ]);
    const csv = [header, ...rows].map((line) => line.map(csvCell).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "batchhelm-inventory.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page-content">
      <div className="page-header">
        <h1>Affected Inventory</h1>
        <div className="search-box inventory-search">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            placeholder="Search inventory..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.currentTarget.value)}
          />
        </div>
      </div>

      <section className="panel inventory-panel full-width" aria-labelledby="inventory-title">
        <div className="panel-header with-actions">
          <h2 id="inventory-title">
            Inventory Items
            <span className="count-badge">{filteredInventory.length}</span>
          </h2>
          <div className="table-actions">
            <div className="segmented" aria-label="Filter inventory by store">
              {(["all", "Store A", "Store B"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={storeFilter === option ? "selected" : ""}
                  onClick={() => setStoreFilter(option)}
                >
                  {option === "all" ? "All" : option}
                </button>
              ))}
            </div>
            <div className="segmented" aria-label="Filter inventory by status">
              {(["all", "quarantined", "review", "clear"] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={statusFilter === option ? "selected" : ""}
                  onClick={() => setStatusFilter(option)}
                >
                  {option === "all" ? "All" : option}
                </button>
              ))}
            </div>
            <button type="button" className="utility-button" onClick={exportInventoryCsv}>
              <Download size={16} />
              Export CSV
            </button>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Store</th>
                <th scope="col">SKU</th>
                <th scope="col">Product</th>
                <th scope="col">Lot</th>
                <th scope="col">On Hand</th>
                <th scope="col">Quarantined</th>
                <th scope="col">Confidence</th>
                <th scope="col">Status</th>
                <th scope="col">Location</th>
              </tr>
            </thead>
            <tbody>
              {filteredInventory.map((row) => (
                <tr key={row.id}>
                  <td>{row.store}</td>
                  <td>{row.sku}</td>
                  <td>{row.product}</td>
                  <td>{row.lot}</td>
                  <td>{row.onHand}</td>
                  <td>{row.quarantined}</td>
                  <td>
                    <span className="confidence">{row.confidence}%</span>
                  </td>
                  <td>
                    <StatusPill status={row.status} />
                  </td>
                  <td>{row.location}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={4}>Showing {filteredInventory.length} items</td>
                <td>{onHandTotal}</td>
                <td>{quarantinedTotal}</td>
                <td colSpan={3} />
              </tr>
            </tfoot>
          </table>
          {filteredInventory.length === 0 ? (
            <p className="empty-note">No inventory items match the current filters.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
