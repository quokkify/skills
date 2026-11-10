# Set up the local sandbox for the Ledger API

This guide gets a fresh laptop ready to run the sample service.

## Steps

1. Install the toolchain:

   ```bash
   brew install python@3.12
   ```

2. Create a virtual environment:

   ```bash
   python3 -m venv .venv
   ```

3. Start the service:

   ```sh
   make run
   ```

## Troubleshooting

If port 8080 is busy, set `PORT=8081` before `make run`.
