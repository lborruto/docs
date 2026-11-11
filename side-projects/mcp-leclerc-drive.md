# mcp-leclerc-drive: filling a Leclerc Drive cart from Claude

An MCP server that lets Claude do the tedious half of the weekly grocery order on E.Leclerc Drive: find the drive, search the shelves and the offers, remember the usual products, fill the cart. It stops there. No tool validates the cart, books a slot or pays; I check the cart and finish on the site myself. It works through my own Chrome, with a profile of its own that I log into once.

Source: <https://github.com/lborruto/mcp-leclerc-drive>

```text
You     Ajoute à mon panier : 2 packs de lait demi-écrémé, du beurre doux et des petits pois surgelés.

Claude  ▸ search_product × 3   ▸ add_many (3 produits)

        3/3 ajout(s) réussi(s) :
        ✓ Lait demi-écrémé UHT Délisse Brique - 6x1L (id=2612) +2 → 2 au panier
        ✓ Beurre Extra fin Les Croisés Doux - 82% MG - 250g (id=2111) +1 → 1 au panier
        ✓ Petits Pois Notre Jardin 600g (id=87001) +1 → 1 au panier
```

## Why continue someone else's project

[skunkobi/mcp-leclerc-drive](https://github.com/skunkobi/mcp-leclerc-drive) did the hard part: it mapped the site (server-rendered ASP.NET pages with product records embedded as JSON, a single cart endpoint taking absolute quantities, a separate store-locator API) and found the only way past DataDome's active mode, which is to be a real browser. Then it stopped being maintained, with two open bug reports that broke it for many stores.

Before using it with my own account I audited it. The code was clean, but a few things I would not run as they were:

- Chrome was started with the usual debug port, 9222, and the server attached to *any* Chrome already listening there, driving its first tab.
- The npm package still shipped a leftover file from the cookie-reading version.
- `add_to_cart` sent the quantity as Leclerc's absolute target, so "add 2" to a line of 2 left it at 2.

So I took it over as a standalone repository (MIT, history kept, credited), fixed it, hardened it, and set it up like my other projects.

## How it works

```
Claude Code ── stdio (MCP) ──▶ mcp-leclerc-drive (Node)
                                   │  one request at a time, 1 s + jitter apart
                                   │  CDP over 127.0.0.1:9333, the server's own tab
                                   ▼
                     Chrome, dedicated profile (~/.mcp-leclerc-drive/chrome)
                                   │  fetch() runs inside the page: real cookies,
                                   │  real TLS fingerprint, DataDome's challenge solved
                                   ▼
                     fdN-courses.leclercdrive.fr · www · api-recherchemagasins
```

### Key choices

- **Nothing past the cart.** A permanent rule, enforced by a contract test that starts the server and checks the exact tool list.
- **A host allowlist checked everywhere.** Before each navigation, before each request, on the page actually reached after redirects, inside the page for redirected requests, and on every host that comes from outside the code (the store locator, `set_store`, the environment, the saved settings). CI also scans the code and the build for any host outside it.
- **Never someone else's Chrome.** The server writes a lock with Chrome's PID, port and DevTools browser id (random per run), and refuses any Chrome on the port that does not match. It refuses to run on the main Chrome, Chromium, Edge or Brave profile on any OS, and works in its own tab.
- **Never the password or the cookies.** I log in myself in the window; requests run in the page, so the browser attaches its own cookies. Nothing reads, stores or logs one.
- **Fixed upstream's two issues.** Stores whose host 302s to another shard (the page must be asked where it landed, and URLs built relative to it), and the first call after ~16 idle minutes, when the host redirects to its `-secure` twin, which an in-page fetch cannot follow (re-navigate and retry once).
- **Clear when something is off.** No drive chosen, nobody logged in, a drive other than the one the Chrome window is on, a page Leclerc changed: each is said as such, with what to do, instead of an empty result. A `diagnostic` tool gives a report that is safe to paste in an issue.
- **Tested against a simulated browser.** Most of the 71 tests run the real session code against a fake Chrome whose in-page script is executed in a `node:vm` sandbox with a same-origin-only fetch, plus a simulated cart. An independent review pass found races (two parallel adds losing one, a `set_store` landing mid-request) that now have tests.
- **Checked on the live site, sparingly.** A few dozen requests in total, on my own cart, which ended exactly as it started. Those runs found what no fake would have: search results included the cart (every page embeds it), an unknown product id comes back as "0 in cart" rather than an error, truck relays share their drive's store id, and a search with no result still returns six unrelated suggestions.
- **Released like the rest.** CI on Linux, macOS and Windows, gitleaks over the history, CodeQL, npm audit, actionlint, every action pinned to a commit at least two weeks old. Releases are a tarball and a one-file Claude Desktop bundle, both with build-provenance attestations, only from tags on `main`, and never on npm (the name there is still upstream's 0.3.0).

## How to run it

You need Google Chrome and a Leclerc Drive account. In Claude Desktop, open the `.mcpb` file of the [latest release](https://github.com/lborruto/mcp-leclerc-drive/releases/latest): no terminal needed. In Claude Code (Node.js 22+):

```bash
claude mcp add --scope user leclerc-drive -- npx -y \
  --package=https://github.com/lborruto/mcp-leclerc-drive/releases/download/v0.5.0/mcp-leclerc-drive-0.5.0.tgz \
  mcp-leclerc-drive
```

Ask Claude for the drives around your postcode: a Chrome window opens, log into Leclerc Drive there and choose your drive, then `set_store` with the id it showed. From then on, « ajoute 2 packs de lait et du beurre » fills the cart, and you check out on the site. The [README](https://github.com/lborruto/mcp-leclerc-drive#get-started) has the clone-based install, other clients' configuration and the settings; there is a [French one](https://github.com/lborruto/mcp-leclerc-drive/blob/main/docs/README.fr.md) too.
