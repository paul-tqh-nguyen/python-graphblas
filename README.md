# Stock Price Comparison

This toy project compares the prices of stocks.

## Development Environment

Using the contents of this repository requires [conda](https://conda.io/projects/conda/en/stable/user-guide/install/download.html). 

Once conda is installed, run the following:

```
conda env create --file environment.yml
conda activate prefect_oa
```

## Example Run

Once the development environment is set up, follow these steps to see some graphs comparing stocks.

Generate the markdown artifacts containing the graphs via:
```
python3 main_flow.py
```

Start a prefect server to see the artifacts.
```
prefect server start
```

It will point to a dashboard via some STDOUT prints like:
```
Check out the dashboard at http://127.0.0.1:4200
```

Visit the link to bring up the dashboard.

There will be a link to the artifacts generated. The url will be something like:
```
http://127.0.0.1:4200/artifacts
```

From there, you'll be able to see some nice graphs. If you don't, please notify me. 