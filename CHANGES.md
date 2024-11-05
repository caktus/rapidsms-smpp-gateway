# Changes

## 1.3.0 (November 5, 2024)

- Handle message decoding more safely (#20)
- Add support for Python 3.12, Django 5.0, and Django 5.1
- Drop support for Python 3.8 and Django 3.2

## 1.2.3 (June 12, 2024)

- Add indexes to speed up finding new messages to process

## 1.2.2 (September 29, 2023)

- Restore management commands `__init__.py` files

## 1.2.1 (September 19, 2023)

- Restore missing migrations files (#18)

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
