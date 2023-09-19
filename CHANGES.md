# Changes

## 1.2.0 (September 19, 2023)

- Add support for Django 4.2 (#16)
- Switch away from Poetry & add support for tox (#17)

## 1.1.0 (June 16, 2023)

- Add support for pinging healthchecks.io from the SMPP client main loop (#15)

## 1.0.4 (May 14, 2023)

- Bug fix: Avoid `IntegrityError` when `short_message` is `None` (#14)

## 1.0.3 (December 20, 2022)

- Add support for graceful termination to `listen_mo_messages` command (#13)

## 1.0.2 (December 6, 2022)

- Add `choices` and admin list filtering for `command_status`
- Add separate admin for `MTMessageStatus` model

## 1.0.1 (December 5, 2022)

- Add support for graceful termination to `smpp_client` command (#10)

## 1.0.0 (November 10, 2022)

- Initial release
