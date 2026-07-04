import hashlib

import requests

from canyin_news.state import ReportState


class DefiniteSendFailure(RuntimeError):
    """钉钉明确拒绝消息，可以在修复原因后重试。"""


class UncertainSendResult(RuntimeError):
    """请求可能已送达，禁止自动重试。"""


def post_markdown(token: str, title: str, text: str) -> dict:
    response = requests.post(
        "https://oapi.dingtalk.com/robot/send",
        params={"access_token": token},
        json={
            "msgtype": "markdown",
            "markdown": {"title": title, "text": text},
        },
        timeout=(3, 20),
    )
    response.raise_for_status()
    return response.json()


def send_to_groups(
    report: str,
    groups: dict[str, str],
    state: ReportState,
    now,
    *,
    title: str = "餐饮AI情报站",
    post_func=post_markdown,
) -> None:
    return _deliver_to_groups(
        report, groups, state, now, title=title, post_func=post_func, reserve=True
    )


def send_reserved_to_groups(
    report: str,
    groups: dict[str, str],
    state: ReportState,
    now,
    *,
    title: str = "餐饮AI情报站",
    post_func=post_markdown,
) -> None:
    return _deliver_to_groups(
        report, groups, state, now, title=title, post_func=post_func, reserve=False
    )


def _deliver_to_groups(
    report,
    groups,
    state,
    now,
    *,
    title,
    post_func,
    reserve,
):
    content_hash = hashlib.sha256(report.encode("utf-8")).hexdigest()[:20]
    failures = []
    for group, token in groups.items():
        if reserve:
            state.reserve(group, content_hash, now)
        elif state.groups.get(group, {}).get("status") != "sending":
            continue
        try:
            result = post_func(token, title, report)
        except (TimeoutError, requests.Timeout, requests.ConnectionError) as exc:
            state.mark_uncertain(group, exc)
            failures.append(UncertainSendResult(f"{group}: {exc}"))
            continue
        except requests.HTTPError as exc:
            state.mark_failed(group, exc)
            failures.append(DefiniteSendFailure(f"{group}: {exc}"))
            continue
        if result.get("errcode") != 0:
            error = f'{result.get("errcode")}: {result.get("errmsg", "unknown error")}'
            state.mark_failed(group, error)
            failures.append(DefiniteSendFailure(f"{group}: {error}"))
            continue
        state.mark_sent(group, now)

    if failures:
        uncertain = next(
            (failure for failure in failures if isinstance(failure, UncertainSendResult)),
            None,
        )
        raise uncertain or failures[0]
