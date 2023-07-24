###########
# Imports #
###########

import base64
from datetime import datetime, timedelta
from enum import Enum
from io import BytesIO
from itertools import product

import bs4
import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import requests
from prefect import flow, get_run_logger, task
from prefect.artifacts import create_link_artifact, create_markdown_artifact
from prefect.tasks import task_input_hash

mpl.use("Agg")

#########
# Utils #
#########


def log(*args, **kwargs) -> None:
    logger = get_run_logger()
    logger.info(*args, **kwargs)
    return


class TickerSymbol(Enum):
    SPY = "SPY"
    VOO = "VOO"
    QQQ = "QQQ"
    NVDA = "NVDA"
    GOOG = "GOOG"

    def get_yahoo_url(self) -> str:
        return f"https://finance.yahoo.com/quote/{self.value}/history?p={self.value}"


def generate_html_for_line_graph(
    left_df: pd.DataFrame,
    right_df: pd.DataFrame,
    left_label: str,
    right_label: str,
    y_col: str,
) -> str:
    title = f"{left_label} {y_col} vs {right_label} {y_col}"
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(left_df.index, left_df[y_col], label=left_label)
    ax.plot(right_df.index, right_df[y_col], label=right_label)
    ax.legend()
    ax.set_xlim(
        left=min(left_df.index.min(), right_df.index.min()),
        right=max(left_df.index.max(), right_df.index.max()),
    )
    ax.set_ylim(bottom=0)
    for tick in ax.get_xticklabels():
        tick.set_rotation(-45)
    fig.suptitle(title)
    tmpfile = BytesIO()
    fig.savefig(tmpfile, format="png")
    encoded = base64.b64encode(tmpfile.getvalue()).decode("utf-8")
    image_html = "<img src='data:image/png;base64,{}'>".format(encoded)
    return image_html


######################
# Flows, Tasks, etc. #
######################


@task(
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=1),
    retries=5,
    retry_delay_seconds=60,
)
def generate_ticker_symbol_df(ticker_symbol: TickerSymbol) -> pd.DataFrame:
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-GB,en;q=0.9,en-US;q=0.8,ml;q=0.7",
        "cache-control": "max-age=0",
        "dnt": "1",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.122 Safari/537.36",
    }
    url = ticker_symbol.get_yahoo_url()
    response = requests.get(url, verify=False, headers=headers, timeout=30)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    trs = (
        tr for tr in soup.select("div#Main table tbody tr") if not "Dividend" in tr.text
    )
    row_dicts = []
    for tr in trs:
        spans = tr.select("td span")
        assert len(spans) == 7
        row_dict = {
            "day": datetime.strptime(spans[0].text, "%b %d, %Y").date(),
            "open_price": float(spans[1].text),
            "high_price": float(spans[2].text),
            "low_price": float(spans[3].text),
            "close_price": float(spans[4].text),
            "adjusted_close_price": float(spans[5].text),
            "volume": float(spans[6].text.replace(",", "")),
        }
        row_dicts.append(row_dict)
    df = pd.DataFrame(row_dicts).set_index("day")
    df["ticker_symbol"] = ticker_symbol.value
    return df


@task
def publish_artifacts_for_dfs(left_df: pd.DataFrame, right_df: pd.DataFrame) -> None:
    [left_ts_string] = left_df["ticker_symbol"].unique()
    [right_ts_string] = right_df["ticker_symbol"].unique()
    assert set(left_df.columns) == set(right_df.columns)

    y_cols = (c for c in right_df.columns if c not in ("day", "ticker_symbol"))
    html_strings = (
        generate_html_for_line_graph(
            left_df,
            right_df,
            left_ts_string,
            right_ts_string,
            y_col,
        )
        for y_col in y_cols
    )
    markdown_string = "\n\n".join(html_strings)
    create_markdown_artifact(
        key=f"{left_ts_string.lower()}-vs-{right_ts_string.lower()}",
        markdown=markdown_string,
        description=f"{left_ts_string} vs {right_ts_string}",
    )
    return


@flow
def generate_report_for_ticker_symbols(
    ts_left: TickerSymbol, ts_right: TickerSymbol
) -> None:
    left_df = generate_ticker_symbol_df(ts_left)
    right_df = generate_ticker_symbol_df(ts_right)
    publish_artifacts_for_dfs(left_df, right_df)
    log(f"Report for {ts_left.value} vs {ts_right.value} is completed.")
    return


@flow
def create_stock_reports() -> None:
    pairs = (
        (ts_left, ts_right)
        for ts_left, ts_right in product(TickerSymbol, TickerSymbol)
        if ts_left.value < ts_right.value
    )
    for ts_left, ts_right in pairs:
        generate_report_for_ticker_symbols(ts_left, ts_right)
    return


if __name__ == "__main__":
    create_stock_reports()
