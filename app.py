import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
import re

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = session["user_id"]
    rows = db.execute("SELECT symbol, name, SUM(shares) AS shares, price FROM Prices WHERE user_id = ? GROUP BY symbol", user)
    rows1 = db.execute("SELECT symbol, name, SUM(shares) AS shares, price FROM transactions WHERE user_id = ? GROUP BY symbol", user)

    rem_cash = db.execute("SELECT cash FROM users WHERE id = ?", user)
    """ This rem_cash gives back a dictionary """
    cash = rem_cash[0]["cash"]
    grand_total = cash

    for row in rows:
        grand_total += row["price"] * row["shares"]

    for row in rows:
        quot = lookup(row["symbol"])
        real_price = db.execute("UPDATE Prices SET price = ? WHERE symbol = ? AND user_id = ?", quot["price"], row["symbol"], user)

    return render_template("portfolio.html", rows=rows, cash=cash, grand_total=grand_total, usd=usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    if request.method == "POST":
        symbol = request.form.get("symbol")
        txt = request.form.get("shares")
        if not txt.isdigit():
            return apology("must provide number", 400)
        shares = int(request.form.get("shares"))
        shares = round(shares)
        if not (symbol):
            return apology("must provide symbol", 400)
        if not (shares):
            return apology("must provide shares", 400)
        if (shares) <= 0:
            return apology("must provide a positive value", 400)
        if (shares) % 1 != 0:
            return apology("must provide a whole number", 400)
        quot = lookup(symbol.upper())
        if quot == None:
            return apology("This symbol does not exist in the exchange", 400)
        grand_total = shares * quot["price"]
        name = quot["name"]
        user = session["user_id"]
        rem_cash = db.execute("SELECT cash FROM users WHERE id = ?", user)
        """ This rem_cash gives back a dictionary """
        cash = rem_cash[0]["cash"]

        if cash < grand_total:
            return apology("Insufficient Funds", 400)

        rem_rem_cash = cash - grand_total
        db.execute("UPDATE users SET cash = ? WHERE id = ?", rem_rem_cash, user)
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time, name) VALUES(?, ?, ?, ?, ?, ?)",
                   user, symbol.upper(), shares, quot["price"], dt_string, quot["name"])
        """ This Database is just for updation of stock prices """
        db.execute("INSERT INTO Prices (user_id, symbol, shares, price, name) VALUES(?, ?, ?, ?, ?)",
                   user, symbol.upper(), shares, quot["price"], quot["name"])
        flash(" Bought! ")
        return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = session["user_id"]
    rows = db.execute("SELECT * FROM transactions WHERE user_id = ?", user)
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    if request.method == "POST":
        symbol = request.form.get("symbol")
        quot = lookup(symbol.upper())
        if quot != None:
            return render_template("quoted.html", quot=quot)
        else:
            return apology("This symbol does not exist in the exchange", 400)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    if request.method == "GET":
        return render_template("register.html")

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # To validate the password
        elif len(request.form.get("password")) < 6:
            return apology("must provide password of at least 6 letters", 400)

        elif re.search('[0-9]', request.form.get("password")) is None:
            return apology("must provide password with Number", 400)

        elif re.search('[A-Z]', request.form.get("password")) is None:
            return apology("must provide password with Capital letters", 400)
        # If the password is of correct format then proceed

        # Ensure re-type password was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password again", 400)

        # Ensure both the passwords match
        elif not (request.form.get("confirmation") == request.form.get("password")):
            return apology("passwords do not match", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username does not exist
        if len(rows) != 0:
            return apology("This Username Already Exists, Please try another name", 400)

        # Hash the password provided by the user
        usr = request.form.get("username")
        passwd = generate_password_hash(request.form.get("password"))

        # Register the new user into the database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", usr, passwd)

        # Redirect user to home page
        return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        user = session["user_id"]
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol HAVING SUM(shares) >= 1", user)
        return render_template("sell.html", symbols=[row["symbol"] for row in symbols])

    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not (symbol):
            return apology("must provide symbol", 400)
        if not (request.form.get("shares")):
            return apology("must provide shares", 400)
        quot = lookup(symbol.upper())
        shares = int(request.form.get("shares"))
        if (shares) <= 0:
            return apology("must provide a positive value", 400)
        if quot == None:
            return apology("This symbol does not exist in the exchange", 400)

        grand_total = shares * quot["price"]
        user = session["user_id"]
        rem_cash = db.execute("SELECT cash FROM users WHERE id = ?", user)
        """ This rem_cash gives back a dictionary """
        cash = rem_cash[0]["cash"]

        rem_shares = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol", user, symbol)
        rem_rem_shares = rem_shares[0]["shares"]
        if shares > rem_rem_shares:
            return apology("Insufficient shares", 400)

        rem_rem_cash = cash + grand_total
        db.execute("UPDATE users SET cash = ? WHERE id = ?", rem_rem_cash, user)
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time, name) VALUES(?, ?, ?, ?, ?, ?)",
                   user, quot["symbol"], shares*(-1), quot["price"], dt_string, quot["name"])
        db.execute("INSERT INTO Prices (user_id, symbol, shares, price, name) VALUES(?, ?, ?, ?, ?)",
                   user, quot["symbol"], shares*(-1), quot["price"], quot["name"])
        flash(" Sold! ")
        return redirect("/")