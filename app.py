import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

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

os.environ['API_KEY'] = "pk_113eb094ac2f4bc884ec7f650394e9cb"
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



# this is a display function. Used to display users details after any changes
@app.route("/")
@login_required
def index(error=None,result=None, addcash=None,code=200):
    user_id = session.get("user_id")
    # retrieve the user details from database
    user = db.execute("SELECT company_name, share, symbol FROM buy WHERE buy_id = ?", user_id)
    total = 0
    # loops add the current price and also 'total' of 'share'* 'the current price'
    for i in range(len(user)):
        symbol = user[i]["symbol"]
        look = lookup(symbol)
        user[i]["price"] = look["price"]
        user[i]["total"] =round((look["price"] * user[i]["share"]),2)
        total += user[i]["total"]

    # retrieves the user current available price
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    cash = cash[0]["cash"]
    # 'grand_price' is the total of all the share * the current price owned by the user
    grand_total = round((cash + total), 2)

    return render_template("index.html",error=error,addcash=addcash, result=result ,amount=cash, user=user, total=total, grand_total=grand_total),code



@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():

    # if the user requests page using a GET method
    if request.method == "GET":
        return index()
    else:
        user_id = session.get("user_id")
        error = None
        tup = list()
        # Get the 'shares & symbol' value from the index page using request.form.get()
        shares = request.form.get("shares")
        symbol = request.form.get("symbol").upper()

        # check if share has a value or greater than or equals to 1.
        if not shares or not int(shares) >= 1:
            error = "shares can't be less than 1"
            return index(error=error,code=400)

        # Checks if  "symbol" has a value .
        if not request.form.get("symbol"):
            error = "please enter a valid symbol"
            return index(error=error, code=400)

        # Gets the curent value for "symbol" from "lookup()" and pass it to "result"
        result = lookup(symbol)

        # if "result" does not have value.
        if not result:
            error = "please enter a valid symbol"
            return index(error=error, code=400)

        # retrieve the amount of "cash" a user-id has from the "user.
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        cash = str(cash[0]["cash"])
        cash = float("".join(cash))

        # total is the the current price of the share multiplied by the number of share the user trying to buy
        total = round(result["price"] * float(shares),2)
        # if the cash is not greater than the
        if not cash >= total:
            error = "insuffiecent funds"
            return index(error=error, code=400)

        # get the current already in the user account
        share = db.execute("SELECT share FROM buy WHERE buy_id = ? AND symbol = ?",user_id,symbol)
        # we store the companyname and the symbol in tup[]
        for key, item in result.items():
            if not key == 'price':
                tup.append(item)

        # remove the amount of cash it takes to buy the share
        cash = round((cash - total),2)

        # if share exist,
        if share:
            # update the user cash
            db.execute("UPDATE users SET cash = ? WHERE id = ?" , cash,user_id)
            share = share[0]["share"] + int(shares)
            # update user current share for a particular symbol
            db.execute("UPDATE buy SET share = ? WHERE buy_id = ? AND symbol =?",share,user_id,symbol )
        else:
            # if share dont exist we add a new stock in the user data space
            db.execute(
                "INSERT INTO buy(buy_id,share,symbol,company_name) VALUES (?,?,?,?)",
                    user_id, int(shares), tup[1],tup[0])
            # updates the user cash
            db.execute("UPDATE users SET cash = ? WHERE id = ?",
                       cash, user_id)
        # add the transaction to the history
        db.execute("INSERT INTO history (users_id, share, symbol,company_name,price,types) VALUES (?,?,?,?,?,?)",
                   user_id, int(shares), tup[1], tup[0], result["price"], "BUY")
    # return to the display function to reflect the changes to screen
    return index()


# display the buy and sell history to screen
@app.route("/history")
@login_required
def history():
    user_id = session.get("user_id")
    # use to display the current cash in the user account to the header
    account = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
    # retrieve the buy and sell data from history database and diplay to the user screen
    sell = db.execute("SELECT sell_id,company_name,symbol,share,price,dates FROM history WHERE users_id =? AND types=?", user_id,"SELL")
    buy = db.execute("SELECT buy_id,company_name,symbol,share,price,dates FROM history WHERE users_id =? AND types=?", user_id,"BUY")
    return render_template("history.html",sell=sell, buy=buy, amount = round((account[0]["cash"]), 2))


@app.route("/login", methods=["GET", "POST"])
def login(open=None):
    """Log user in"""
    # check if a user if logging in or changing password
    if not open:
        # Forget any user_id
        session.clear()

    error = None
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            error = "Wrong username or password"
            return render_template("login.html", error=error)

        # Ensure password was submitted
        elif not request.form.get("password"):
            error = "Wrong username or password"
            return render_template("login.html", error=error)

        user = request.form.get("username")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            error = "Wrong username or password"
            return render_template("login.html", error=error, user=user)

        # check if a user is logging in or changing password
        if not open:
            # Remember which user has logged in
            session["user_id"] = rows[0]["id"]

            # Redirect user to home page
            return redirect("/")
        else:
            return True
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html",)


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
    error = None
    # gets the quote passed by the user
    sym = request.form.get("symbol").strip()
    # if its a POST request
    if request.method == "POST":
        # if the user did not passed a value
        if not sym:
            error = " Input a symbol to get a Quote"
            return index(error=error, code=400)
        # get the current value of the symbol from lookup()
        result = lookup(sym)
        # if results did not return a value
        if not result:
            error = "unknown symbol"
            return index(error=error, code=400)

        # passed the result to index() to display
        return index(result=result)
    else:
        return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    #user reached via POST
    error = None
    if request.method == "POST":
        confirm = request.form.get("confirmation")
        passed = request.form.get("password")
        username = request.form.get("username").strip()

        # the if statement evaluates the the username and password
        if not username:
            error = "enter a username"
            return render_template("register.html", error=error,user=username),400

        elif not passed:
            error = "enter a password"
            return render_template("register.html", error=error,user=username),400

        # checks if password and confirmation are the same
        if passed != confirm:
            error = "password do not match"
            return render_template("register.html", error=error,user=username),400
        # make sure the password is greater than or equal to 6
        if not len(username) >= 6:
            error = "username is short atleast 6 letters"
            return render_template("register.html", error=error,user=username),400
        # make the password is greater than or equals 6
        if not len(passed) > 6 and not len(confirm) > 6:
            error = "length password has to be greater than 6"
            return render_template("cpassword.html", error=error, next="yes")
        # checks if a username exist.
        user = db.execute("SELECT username FROM users WHERE username = ?", username)
        if user:
            error = "username already exit"
            return render_template("register.html", error=error,user=username),200
        # insert the new users information to the database
        db.execute("INSERT INTO users (username, hash) VALUES (?,?)",username,
                generate_password_hash(passed))
        flash("succesfully Register, Login in with your Username and password")
        return redirect("/")

    else:
        return render_template("register.html")


# this function validate the sell button
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # the function requires the current user_id
    user_id = session.get("user_id")
    # check if it a GET o
    if request.method == "GET":
        return redirect("/")
    else:
        # get the respond from the user
        symbol = request.form.get("symbol")
        share = request.form.get("share")
        error = None
        # if the user did not pass the correct symbol or share
        if not symbol or not share or not share.isdigit() :
            error= " input the correct symbol or share"
            return index(error=error, code = 400)

        # retrieve the user information from the database for revalidation
        getShare = db.execute("SELECT symbol, share, company_name FROM buy WHERE buy_id = ? AND symbol = ?",user_id,symbol)
        share = int(share)

        # checks if share is less than 1 or dont have that particular share in the account
        if not share >= 1 or not getShare or getShare[0]["share"] < share:
            error = "please choose a correct stock you own"
            return index(error=error, code=400)

        # retrieve the current cash the user has in account
        cash = db.execute("SELECT cash FROM users WHERE id = ?",user_id)

        # get the current price of the symbol
        look = lookup(symbol)

        # insert into history and sold database for keping records
        db.execute(
        "INSERT INTO sold (sell_id, share, symbol, company_name) VALUES (?,?,?,?)",
            user_id, share, getShare[0]["symbol"], getShare[0]["company_name"])

        # if the current share the user has equals to how much share the user is trying to sell we completely delete from the buy record
        # if the share in record is bigger we deduct it
        if getShare[0]["share"] == share:
            db.execute("DELETE FROM buy WHERE buy_id = ? AND symbol = ?", user_id, symbol)
        else:
            newShare = getShare[0]["share"] - share
            db.execute("UPDATE buy SET share = ? WHERE buy_id = ? AND symbol = ?", newShare, user_id,symbol)
        # we update the current price after sales
        cash = db.execute("SELECT cash FROM users WHERE id = ?",user_id)
        cash = round((cash[0]["cash"]) + look["price"] * share,2)

        db.execute("UPDATE users SET cash = ? WHERE id = ? ", cash, user_id)
        trans = db.execute("SELECT trans_id FROM sold WHERE sell_id =? AND share =? AND symbol=? AND company_name =?",
                           user_id, share, getShare[0]["symbol"], getShare[0]["company_name"])
        # update the history
        db.execute(
            "INSERT INTO history (users_id,sell_id,share,symbol,company_name,price,types) VALUES (?,?,?,?,?,?,?)",
                   user_id, trans[0]["trans_id"], int(share), getShare[0]["symbol"], getShare[0]["company_name"],look["price"], "SELL")
        return redirect("/")


# this function is used to change password
@app.route("/cpassword", methods=["GET", "POST"])
@login_required
def cpassword():
    user_id = session.get("user_id")
    error = None

    # if the request is a post
    if request.method == "POST":
        # if user is required to login first and login return True
        if request.form.get("login") == "login" and login( open= True):
            return render_template("cpassword.html", first=None, next="yes" )
        # if login return true then the user can change the password
        elif request.form.get("changepassword") == "changepassword":
            # confirm and passed collects the value passed by the user for confirmation and change of password
            confirm = request.form.get("confirmation")
            passed = request.form.get("password")
            # if do not pass a value for passesd or confirm
            if not passed and not confirm:
                error = "enter a password"
                return render_template("cpassword.html", error=error, next="yes")
            # if they do not match
            if passed != confirm:
                error = "password do not match"
                return render_template("cpassword.html", error=error, next="yes")
            # if the user did not pass a password which legnth is greater than 6
            if not len(passed) > 6 and not len(confirm) > 6:
                error = "length password has to be greater than 6"
                return render_template("cpassword.html", error=error, next="yes")
            # updates the old password with new password
            db.execute("UPDATE users SET hash = ? where id = ?",
                            generate_password_hash(passed), user_id)
            # AS the user to login with the new password
            return render_template("login.html")
        else:
            # return error if the user fail to provid a valid password or username
            error = "type in a correct password"
            return render_template("cpassword.html", error=error, first="yes")
    else:
        # if the request is a GET
        return render_template("cpassword.html", first="yes")



# serves as function where a user can add cash to their account
@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    # if the request is a POST
    if request.method == "POST":
        # gets the current loggin user and the amount
        # funds the user is trying to transfer their account
        user_id = session.get("user_id")
        fund = request.form.get("fund")
        # error message to be passed if the user pass a wrong input
        error = None
        fund = check_float(fund)
        # if fund was not passed or it less than 1
        if not fund:
            error = "please enter a correct amount to add to your account"
            return index(error=error, code=400)

        # get the amount of cash user has in account
        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)
        # add the new cash with the prvious amount
        fund = cash[0]["cash"] + fund
        # update the database with the new amount
        db.execute("UPDATE users SET cash = ? where id = ?",fund, user_id)
        # redict the user back to the main page this could either be the buy or sell
        return redirect("/")
    else:
        # if the request is  a GET
        return index(addcash="yes")

# check if a string is a floating number
# https://www.delftstack.com/howto/python/string-is-a-valid-float/#:~:text=true%20if%20otherwise.-,Use%20the%20isdigit()%20and%20partition()%20Functions%20to%20Check,character%20is%20not%20a%20digit.
def check_float(element):
    divided = element.partition('.')

    if element.isdigit():
      element = float(element)
      return element

    elif (divided[0].isdigit() and divided[1] == '.' and divided[2].isdigit()) or (divided[0] == '' and divided[1] == '.' and divided[2].isdigit()) or (divided[0].isdigit() and divided[1] == '.' and divided[2] == ''):
            element = float(element)
            return element
    else:
        return False