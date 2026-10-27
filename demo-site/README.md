# Lemon Stand: demo site for Tag Health Check

A fictional lemonade shop with simulated Adobe tags and deliberate tagging mistakes.
`js/launch-lemonstand.min.js` stands in for a self-hosted Adobe Launch library: it creates
`window._satellite` and sends Adobe Analytics style beacons to this site's own `/b/ss/` path.
All links are relative, so the folder works on any static host (Netlify, GitHub Pages, S3).

## Pages to paste into Run Audit (in this order)

    https://<your-site>/
    https://<your-site>/products/classic-lemonade.html
    https://<your-site>/products/strawberry-lemonade.html
    https://<your-site>/about.html
    https://<your-site>/cart.html
    https://<your-site>/checkout/thank-you.html

Keep cart before thank-you: the duplicate order ID check depends on that order.

## Answer key (9 findings, pass rate 70%)

| Page | Planted mistake | Finding |
|---|---|---|
| Home | none, the healthy page | passes everything |
| Classic lemonade | page view beacon sent twice | Critical, Duplicate fires |
| Classic lemonade | `productName`, `cupSize` keys | Warning, Naming convention |
| Classic lemonade | `product_id: ""` | Critical, Variable integrity |
| Strawberry lemonade | beacon fires, Launch loads 300 ms later | Critical, Load order |
| Our story (about) | no tags on the page at all | Critical, Tag presence (page view) |
| Cart | order ID assigned early | passes, sets up the thank-you finding |
| Thank you | purchase never sent to Adobe | Critical, Tag presence (purchase) |
| Thank you | purchase pushed twice | Critical, Duplicate fires |
| Thank you | `revenue: "undefined"` | Critical, Variable integrity |
| Thank you | reuses order ID ORD-1042 from the cart | Critical, Variable integrity |
