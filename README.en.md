# Xbox Port MCP

[Español](README.md)

Independent stdio MCP server for original Xbox inspection and **game-specific** Windows port recipes. Not a universal ISO-to-native converter.

Experimental 0.1.0 includes `sims-bustin-out-usa`, pinning [bustinout-recomp](https://github.com/abilliontokens/bustinout-recomp) and [XboxXBERecomp](https://github.com/abilliontokens/XboxXBERecomp). The original manual workflow was reported playable by its user, including a household, saves, Spanish game text and installation. This new MCP has automated protocol/parser/path/job/packaging tests; a complete game build through it has not yet been replayed. Historical observations are labelled separately.

Bring your own local files. No retail ISO, XBE, assets, screenshots, BIOS, keys, saves or rebuilt game binaries are included. Spanish mode selects shipped game resources; the extra PC settings overlay translation is not part of this recipe. The installer currently uses Spanish.

## Install

Requires Python 3.11+. In a cloned repository:

```console
python -m venv .venv
.venv\Scripts\python -m pip install .
```

Use `.venv/bin/python` on POSIX. Connect your MCP client to that interpreter with arguments `-m xbox_port_mcp`; edit [examples/mcp.json](examples/mcp.json). See [configuration](docs/configuration.md) for switches and prerequisites. Inspection/extraction are portable; the current build and packaging recipe targets Windows x64.

External execution is off by default. Source fetching needs a separate network opt-in. Git, CMake, Ninja, compatible LLVM, an x64 MSVC environment, FFmpeg, Inno Setup, licensed CRT redistributables and PowerShell/IMAPI are installed separately as needed. Build scripts run as trusted user code, not inside a security sandbox.

## Workflow

Call `doctor`, `list_profiles`, `inspect_iso`, then `create_workspace`. Run `start_step`: `extract` (with `input_path`), `prepare`, `configure`, `compile`. Preparation/configuration apply fixes automatically. Poll `get_job`; use `cancel_job` for owned jobs. Ask the user to test the game and saving/reloading; record only their actual observations with `record_manual_observation`. Then run `artwork`, `installer`, `iso`, `verify_iso` and test installation. Compilation success never proves playability.

Nine tools, the `xbox-port://profiles` resource and the `port_workflow` prompt are exposed. Recipes are bundled; clients cannot submit shell commands or repository URLs. Job IDs belong to one server session; workspaces remain on disk after restart.

## Contribute

Run `python -m pip install ".[dev]"` and `python -m pytest -q`. Tests use synthetic data only. [CONTRIBUTING.md](CONTRIBUTING.md) explains new profiles: a JSON entry alone cannot implement a port.

Own code: [MIT](LICENSE). [Third-party attribution](THIRD_PARTY.md). External projects retain their own licenses and are fetched separately.
