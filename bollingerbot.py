from yfapi  import YahooFinanceAPI, Interval
import datetime
import matplotlib.pyplot as plt
import pandas as pd

def get_sma(data, period):
    return data.rolling(window=period).mean()

def get_bollinger_bands(data, sma, periods):
    std = data.rolling(window=periods).std()
    upper = sma + std * 2
    lower = sma - std * 2
    return upper, lower

def get_buy_sell_points(data):
    # iterate the dataset, check for cross above upper and below lower bb
    trades = {
        "buy_indices": [],
        "sell_indices": [],
        "sell_prices": [],
        "buy_prices": []
    }
    for idx, row in data.iterrows():
        if idx == 0:
            continue

        # above upper band
        if row["upper"] < row["Close"] and row["upper"] > data.loc[idx-1]["Close"]:
            # no short selling, just sell the shares previously purchased
            if len(trades["buy_indices"]) == 0:  
                continue
            elif len(trades["sell_indices"]) > 0 and trades["buy_indices"][len(trades["buy_indices"]) - 1] < trades["sell_indices"][len(trades["sell_indices"]) - 1]:
                # have we bought since the last sell?
                continue

            trades["sell_indices"].append(idx)
            trades["sell_prices"].append(row["Close"])
            # print(idx, "top", row["Close"], row["upper"], row["Date"])
        
        # below lower band
        if row["lower"] > row["Close"] and data.loc[idx-1]["lower"] < data.loc[idx-1]["Close"]:
            trades["buy_indices"].append(idx)
            trades["buy_prices"].append(row["Close"])
            # print(idx, "bottom", row["Close"], row["lower"], data.loc[idx-1]["Close"], row["Date"])

    return trades

def calculate_profits(trades, ticker, base_dir):
    # iterate buy/sell lists
    sell_idx = 0
    buy_idx = 0
    avg_price = 0
    total_profit = 0 
    ret = 0
    buy_count = 0
    trade_count = 0
    with open(base_dir + "trades/{}.trades".format(ticker.upper()), 'w') as f:
        while buy_idx < len(trades["buy_indices"]):
            # get average price of all buys before a sell
            avg_price += trades["buy_prices"][buy_idx]
            buy_count += 1  # in case we buy more than once before a sell

            # is the next sell before the next buy? what's our next trade
            if (buy_idx + 1) < (len(trades["buy_indices"]))  and \
                sell_idx < (len(trades["sell_indices"])) and \
                trades["sell_indices"][sell_idx] < trades["buy_indices"][buy_idx + 1]:    
                # sell all shares at sell point
                price = avg_price / buy_count
                profit = (trades["sell_prices"][sell_idx] - price) 
                ret += profit / price # % return
                total_profit += profit
                trade_count += 1

                f.write("Selling {} shares at {} with an avg price of {} for a return of {} and profit of {}. (indicies buy/sell: {}/{})".format(
                    buy_count, trades["sell_prices"][sell_idx], price, profit/price, profit, trades["buy_indices"][buy_idx], trades["sell_indices"][sell_idx]))
                f.write("\n")

                # reset variables
                buy_count = 0
                avg_price = 0
                sell_idx += 1

            buy_idx += 1
        if sell_idx < len(trades["sell_indices"]) and buy_count > 0:
            # sell any remaining shares 
            price = avg_price / buy_count
            profit = (trades["sell_prices"][sell_idx] - price) 
            ret += profit / price # % return
            total_profit += profit
            trade_count += 1
            f.write("Selling {} shares at {} with an avg price of {} for a return of {} and profit of {}. (indicies buy/sell: {}/{})".format(
                    buy_count, trades["sell_prices"][sell_idx], price, profit/price, profit, trades["buy_indices"][buy_idx-1], trades["sell_indices"][sell_idx]))
            f.write("\n")


    if trade_count > 0:
        ret /= trade_count
    return ret, total_profit

if __name__ == '__main__':
    base_dir = "./BollingerBot/"
    img_dir = base_dir + "imgs/"
    tickers = pd.read_csv(base_dir + "sp500tickers.csv")["symbol"].tolist()
    # tickers=["AAPL"]
    end_dt = datetime.datetime.today()
    start_dt = datetime.datetime(end_dt.year - 10, end_dt.month, end_dt.day)
    api = YahooFinanceAPI(Interval.DAILY)

    progress_count = 1
    results_dict = {
        "ticker": [],
        "profit": [],
        "avg_return": [],
        "start_price": []
    }
    for ticker in tickers:
        print("Processing ticker symbol {} ({} out of {}).".format(ticker.upper(), progress_count, len(tickers)))
        try:
            data = api.get_ticker_data(ticker, start_dt, end_dt)
        except:
            progress_count += 1
            continue

        data['ma'] = get_sma(data["Close"], 20) # get 20-period SMA
        data['upper'], data['lower'] = get_bollinger_bands(data['Close'], data['ma'], 20)

        data['Close'][20:].plot(label='close', color='darkcyan')
        data['ma'].plot(label='mid', linestyle='--', linewidth='0.9', color='darkturquoise')
        data['upper'].plot(label='upper', linestyle='--', linewidth='1.1', color='indianred')
        data['lower'].plot(label='lower', linestyle='--', linewidth='1.1', color='lightgreen')

        trades = get_buy_sell_points(data)
        avg_return, profit = calculate_profits(trades, ticker, base_dir)
        results_dict["ticker"].append(ticker.upper())
        results_dict["profit"].append(profit)
        results_dict["avg_return"].append(avg_return)
        results_dict["start_price"].append(data.loc[0]["Close"])

        print("Average return per trade: {}\t\tTotal profit trading one share: {}".format(avg_return, profit))

        plt.scatter(trades["buy_indices"], trades["buy_prices"], marker="^", color="darkgreen", s=100, label="buy")
        plt.scatter(trades["sell_indices"], trades["sell_prices"], marker="v", color="darkred", s=100, label="sell")
        plt.title("Bollinger Bands w/ Trades for {}".format(ticker.upper()))
        plt.legend(loc='upper left')
        plt.savefig(img_dir + "{}_plot.png".format(ticker.upper()))
        # plt.show()
        plt.clf()
        progress_count += 1
    
    results_df = pd.DataFrame.from_dict(results_dict)
    results_df.to_csv(base_dir + "results.dat", index=False)
    