# rapidsms-smpp-gateway

A [RapidSMS](https://rapidsms.readthedocs.io/en/latest/) SMPP gateway.

## Management commands

### `smpp_client`

Start an SMPP client instance:

```shell
python manage.py smpp_client smppsim
```

Example configuration using environment variables:

```shell
export PGDATABASE=libya_elections
export DATABASE_URL=postgresql://localhost/$PGDATABASE
export SMPPLIB_HOST=localhost
export SMPPLIB_PORT=2775
export SMPPLIB_SYSTEM_ID=smppclient1
export SMPPLIB_PASSWORD=password
export SMPPLIB_SUBMIT_SM_PARAMS='{"foo": "bar"}'
```

### `listen_mo_messages`

Listen for mobile-originated (MO) messages:

```shell
python manage.py listen_mo_messages --channel new_mo_msg
```

## Publish

1. Update `pyproject.toml` with the version number
2. Update `CHANGES.md` with release notes
3. Create a new release and tag on GitHub. A `publish` Github Actions workflow is configured to run on tag creation.

Or use Poetry's [publish](https://python-poetry.org/docs/cli/#publish) command:
   ```sh
   poetry config pypi-token.pypi <get-from-pypi>
   poetry build
   poetry publish
   ```
