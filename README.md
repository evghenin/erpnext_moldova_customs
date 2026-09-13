### ERPNext Moldova Customs

Moldova customs declarations integration for ERPNext

- Agent rules: [AGENTS.md](AGENTS.md)
- V1 product plan (signed SAD PDF, reconciliation, posting): [docs/v1-plan.md](docs/v1-plan.md)
- V2 product plan (scanned paper + AI, same hub): [docs/v2-plan.md](docs/v2-plan.md)

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/evghenin/erpnext_moldova_customs --branch develop
bench install-app erpnext_moldova_customs
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/erpnext_moldova_customs
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
