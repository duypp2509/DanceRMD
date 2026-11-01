# Contributing

Thanks for helping improve DanceRMD! Bug reports, translations and pull requests are all welcome.

## Reporting bugs and ideas

Open an [issue](https://github.com/duypham-dev/DanceRMD/issues/new/choose) and include:

- the DanceRMD version (dashboard footer), Windows version and GPU,
- the phone model and browser, and whether you used the Wi-Fi or the remote link,
- what you did, what you expected and what happened,
- the relevant part of `%APPDATA%\DanceRMD\dancermd.log`.

Security problems should be reported privately: see [SECURITY.md](SECURITY.md).

## Making a change

1. Fork the repository and create a branch from `main`.
2. Set up the environment as described in [docs/development.md](docs/development.md).
3. Keep the change focused. Match the style of the surrounding code and keep comments in English.
4. Add or update tests, then run `pytest` and `ruff check .`.
5. Any new user-facing text goes into both locale files (and `dancermd/i18n.py` for the desktop shell).
6. Describe the change and how you tested it in the pull request. UI changes benefit from screenshots
   in portrait and landscape.

## Commit messages

The history follows [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(switcher): close windows from the grid
fix(capture): fall back to GDI when DXGI loses the output
docs: explain the remote access trade-offs
```

## License

By contributing you agree that your contributions are licensed under the [MIT License](LICENSE).
