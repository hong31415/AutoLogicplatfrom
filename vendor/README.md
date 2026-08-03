# Optional vendor integrations

This directory intentionally does not contain third-party proprietary SDK binaries.

To use iFinD, obtain the official SDK under your own license and place it locally under `vendor/ifind-sdk/`, or make `iFinDPy` available in the Python environment. Then set the following values in `backend/.env`:

```dotenv
SUBDFA_IFIND_ENABLED=true
IFIND_USERNAME=
IFIND_PASSWORD=
```

The complete `vendor/ifind-sdk/` directory is ignored by Git so account data, logs, binaries, and licensed resources cannot be committed accidentally.
