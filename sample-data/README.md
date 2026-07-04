# BatchHelm Sample Recall Packet

This synthetic packet demonstrates BatchHelm's reviewed incident-intake flow
without using customer or supplier data.

## Files

- `recall-notice-spinach.pdf`: one-page Central Farms supplier notice for
  Spinach 10 oz, reference `CF-2026-06-18`.
- `inventory-spinach.csv`: six valid inventory rows across Store A and Store B.
- `inventory-spinach-invalid.csv`: the same valid rows followed by one negative
  quantity and one duplicate inventory identity.
- `store-b-cooler-spinach.png`: Store B cooler evidence showing product
  `Spinach 10 oz`, lot `L2418`, and UPC `008500001010`.

## Expected Results

The valid export imports six rows, two stores, and 23 on-hand units. The recall
criteria contain lots `L2418`, `L2419`, `L2420`, `L2421`, and `L2422`. The
invalid export keeps the six valid rows and reports two rejected rows with two
review warnings.

## Browser Walkthrough

1. Start the API and web application, then select **New recall**.
2. Upload `recall-notice-spinach.pdf` as the supplier notice.
3. Upload `inventory-spinach.csv` as the inventory export.
4. Add `store-b-cooler-spinach.png` as optional shelf evidence.
5. Process the packet and review the extracted criteria, 23-unit inventory
   total, source provenance, and shelf observation.
6. Confirm the evidence and launch the agent workflow.
7. Repeat with `inventory-spinach-invalid.csv` to demonstrate safe row
   rejection and warning review.

These fixtures were created for BatchHelm and are covered by the repository
MIT license.
