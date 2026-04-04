# FlatOut 2 Splitscreen Enabler

Play FlatOut 2 in local splitscreen by running multiple game instances side-by-side with virtual LAN networking, automatic window management, and controller support.

Inspired by [MorMund/FO2-Splitscreen](https://github.com/MorMund/FO2-Splitscreen), reimplemented in Python.

## Requirements

- Windows 10/11
- Python 3.11+ (make sure "Add to PATH" is checked during install)
- FlatOut 2 (retail, GOG, or Steam)

## Installation

```
pip install -r requirements.txt
```

## Usage

```
python -m fo2_splitscreen launch --game-dir "C:\Games\FlatOut2" --players 2
```

This backs up your saves, launches two windowed instances side-by-side, skips intros, and restores everything on Ctrl+C.

For 4 players (2x2 grid):

```
python -m fo2_splitscreen launch --game-dir "C:\Games\FlatOut2" --players 4
```

### In-Game

1. In each instance go to **Multiplayer > LAN**
2. Left window: **Create Game**
3. Right window: **Join**

### Config File

Save settings for repeated use:

```
python -m fo2_splitscreen config --output session.yaml
python -m fo2_splitscreen launch --config session.yaml
```

Example `config.yaml`:

```yaml
game_dir: "C:\\Games\\FlatOut2"
instance_count: 2
resolution: [640, 480]
skip_intros: true
window_positions: []  # empty = auto layout
network:
  host_port: 23756
  game_port: 23757
  port_stride: 4
```

### Controllers

```
python -m fo2_splitscreen controllers
```

### Launch Options

| Flag | Description | Default |
|------|-------------|---------|
| `-g`, `--game-dir` | Path to FlatOut 2 folder | required |
| `-p`, `--players` | Number of players (1-8) | 2 |
| `-r`, `--resolution` | Resolution per player (WxH) | 640x480 |
| `-c`, `--config` | Config YAML path | — |
| `--no-skip-intros` | Don't skip intro videos | false |

## Troubleshooting

- **Game not windowed:** Set windowed mode in-game first (Options > Video), then use this tool.
- **LAN not finding host:** Allow FlatOut2.exe through Windows Firewall when prompted.
- **Memory patching fails:** Run Command Prompt as Administrator. Addresses are for FlatOut 2 v1.2 — use `--no-skip-intros` if your version differs.
- **Saves corrupted:** Originals are backed up as `Savegame/*.bak.fo2ss` and restored on exit.

## How It Works

Works externally (no DLL injection): patches `device.cfg`/`options.cfg` per instance, manages windows via Win32 API, relays UDP traffic between instances for LAN discovery, and optionally maps controllers to keyboard input via `SendInput`.

## License

MIT
