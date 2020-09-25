import os
import requests

from cs50 import SQL
from flask import Flask, flash, json, jsonify, redirect, render_template, request, session
from flask_session import Session
from functools import wraps
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///imdb.db")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    username = request.form.get("username")
    name = db.execute("SELECT username FROM users")
    match = False # test condition for checking if username is already in use
    passwordMatch = 1 # test condition for checking that passwords match

    if request.method == "POST":

        # Insert into database
        for users in name:
            if username == users["username"]:
                match = True

        if not match:
            if request.form.get("password") == request.form.get("confirmation"):
                db.execute("INSERT INTO users (username, hash, city, country) VALUES (:username, :hash, :city, :country)", username=request.form.get("username"),
                hash=generate_password_hash(request.form.get("password")), city=request.form.get("city"), country=request.form.get("country"))

                rows = db.execute("SELECT id FROM users WHERE username = :username", username=request.form.get("username"))
                # Remember which user has logged in
                session["user_id"] = rows[0]["id"]

                # Redirect user to home page
                return render_template("home.html")

            else:
                return render_template("register.html", passwordMatch=passwordMatch)

        else:
            return render_template("register.html", match=match, username=username, name=name)

    else:
        return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # test conditions for username and password checks
        name_match = 1
        pass_match = 1

        # Ensure username exists and password is correct
        if len(rows) != 1:
            name_match = 2

        if not rows or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            pass_match = 2

        # Redirect user to home page
        if name_match == 1 and pass_match == 1:
            # Remember which user has logged in
            session["user_id"] = rows[0]["id"]
            return redirect("/")
        else:
            return render_template("login.html", x=name_match, y=pass_match)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/", methods=["GET", "POST"])
@login_required
def home():
    ''' Homepage with visual, where you can search a movie to rate '''

    session.pop("title", None) # clear session of last movie title and year
    session.pop("year", None)
    session.pop("name", None)

    if request.method == "POST":

        titles = db.execute("SELECT title FROM movies")

        title_list = [] # list to check if search is valid
        not_found = True # test condition for whether search input is a valid movie
        match = False

        for movie in range(0, len(titles)):
            title_list.append(titles[movie]["title"].lower())  # test search against case insensitive titles

            if titles[movie]["title"].lower() == request.form.get("search").lower():
                match = True
                x = movie # variable to match indexes of titles

        if match:

            name = titles[x]["title"]

            multi = db.execute("SELECT title, year FROM movies WHERE title = :title", title = name)

            if len(multi) > 1:
                multiple = [] # check for multiple movies of the same name
                for movie in multi:
                    year = movie["year"]
                    session["name"] = name # add movie title to session in order to render to confirm function
                    multiple.append(str(f"{name} ({year})"))

                return render_template("confirm.html", multi=multi)

            else:
                year = multi[0]["year"]
                full = str(f"{name} ({year})")
                session["title"] = full # add movie title to session in order to render to rate function
                session["year"] = year
                session["name"] = name # movie title without year attached - for obtaining imdb rating

                return render_template("rate.html", full=full)

        else:
            return render_template("home.html", not_found=not_found)

    else:

        return render_template("home.html")

@app.route("/mylist", methods=["GET", "POST"])
@login_required
def mylist():

    rows = db.execute("SELECT * FROM films WHERE id=:id ORDER BY rating DESC", id=session["user_id"])

    return render_template("mylist.html", rows=rows)


@app.route("/rate", methods=["GET", "POST"])
@login_required
def rate():

    if request.method == "POST":

        num = db.execute("SELECT id FROM movies WHERE title=:title AND year=:year", title=session["name"], year=session["year"])
        rating = db.execute("SELECT rating FROM ratings WHERE movie_id=:id", id=num[0]["id"])

        if request.form.get("comments"):
            db.execute("INSERT INTO films (id, title, rating, comments, imdb) VALUES (:id, :title, :rating, :comments, :imdb)", id=session["user_id"],
                            title=session["title"], rating=float(request.form.get("rating")), comments=request.form.get("comments"), imdb=rating[0]["rating"])
        else:
            db.execute("INSERT INTO films (id, title, rating, comments, imdb) VALUES (:id, :title, :rating, 'No comments', :imdb)", id=session["user_id"],
                                                                     title=session["title"], rating=request.form.get("rating"), imdb=rating[0]["rating"])

        rows = db.execute("SELECT * FROM films WHERE id=:id ORDER BY rating DESC", id=session["user_id"])

        return render_template("mylist.html", rows=rows)

    else:

        return render_template("rate.html")

@app.route("/confirm", methods=["GET", "POST"])
def confirm():

    if request.method == "POST":

        year = request.form.get("confirmed")
        name = session["name"]  # take title saved in home function for multiple films
        full = str(f"{name} ({year})")
        session["title"] = full
        session["year"] = year

        return render_template("rate.html", full=full)

    else:

        return render_template("confirm.html")

@app.route("/myaccount", methods=["GET", "POST"])
def myaccount():
    """Account info and accounts following"""

    session.pop("follow", None) # clear last user followed

    if request.method == "POST":

        # test condition for searching for users to follow - if user does not exist
        check = db.execute("SELECT username FROM users")
        check_list = []
        not_found = False

        for users in check:
            check_list.append(users["username"])

        user = request.form.get("follow") # this means the user is trying to follow someone
        view = request.form.get("followList") # this means the user is trying to view the list of someone they follow

        if user:

            if user in check_list:

                session["follow"] = user # save user searched for to use in follow
                account = db.execute("SELECT id, username, city, country FROM users WHERE username=:username", username=user)

                # swap comments tags for the favorite film of user following in the list to be rendered to the html page
                top = db.execute("SELECT title, rating FROM films WHERE id=:id ORDER BY rating DESC", id=account[0]["id"])
                name = top[0]["title"]
                rating = top[0]["rating"]
                full = str(f"{name}  |  {rating}")
                account[0]["id"] = full

                return render_template("follow.html", account=account)

            else:

                not_found = True

                info = db.execute("SELECT username, hash, city, country FROM users WHERE id=:id", id=session["user_id"])
                x = db.execute("SELECT following FROM follows WHERE user=:user", user=session["user_id"])
                top = db.execute("SELECT title, rating FROM films WHERE id=:id ORDER BY rating DESC", id=session["user_id"])

                # swap comments tags for the favorite film of user following in the list to be rendered to the html page
                name = top[0]["title"]
                rating = top[0]["rating"]
                full = str(f"{name}  |  {rating}")
                info[0]["hash"] = full

                follows = []

                for user in x:
                    y = db.execute("SELECT username, hash, city, country FROM users WHERE id=:id", id=user["following"])

                    top = db.execute("SELECT title, rating FROM films WHERE id=:id ORDER BY rating DESC", id=user["following"])
                    name = top[0]["title"]
                    rating = top[0]["rating"]
                    full = str(f"{name}  |  {rating}")
                    y[0]["hash"] = full
                    follows.append(y)

                # Autocomplete bar for following new accounts
                accounts = db.execute("SELECT username FROM users WHERE username != :username", username=info[0]["username"])
                names = []

                for x in accounts:
                    names.append(x["username"])

                return render_template("myaccount.html", names=names, info=info, follows=follows, not_found=not_found)


        elif view:

            user = db.execute("SELECT id FROM users WHERE username=:username", username=view)
            rows = db.execute("SELECT * FROM films WHERE id=:id ORDER BY rating DESC", id=user[0]["id"])

            return render_template("followlist.html", view=view, rows=rows)

    else:

        info = db.execute("SELECT username, hash, city, country FROM users WHERE id=:id", id=session["user_id"])
        x = db.execute("SELECT following FROM follows WHERE user=:user", user=session["user_id"])
        top = db.execute("SELECT title, rating FROM films WHERE id=:id ORDER BY rating DESC", id=session["user_id"])

        # swap comments tags for the favorite film of user following in the list to be rendered to the html page
        name = top[0]["title"]
        rating = top[0]["rating"]
        full = str(f"{name}  |  {rating}")
        info[0]["hash"] = full

        follows = []

        for user in x:
            y = db.execute("SELECT username, hash, city, country FROM users WHERE id=:id", id=user["following"])

            new = db.execute("SELECT title, rating FROM films WHERE id=:id ORDER BY rating DESC", id=user["following"])
            name = new[0]["title"]
            rating = new[0]["rating"]
            full = str(f"{name}  |  {rating}")
            y[0]["hash"] = full
            follows.append(y)

        # Autocomplete bar for following new accounts
        accounts = db.execute("SELECT username FROM users WHERE username != :username", username=info[0]["username"])
        names = []

        for x in accounts:
            names.append(x["username"])

        return render_template("myaccount.html", names=names, info=info, follows=follows)

@app.route("/follow", methods=["GET", "POST"])
def follow():

    if request.method == "POST":
        follow = db.execute("SELECT id FROM users WHERE username=:username", username=session["follow"])
        user = db.execute("SELECT user FROM follows")
        rows = db.execute("SELECT * FROM films WHERE id=:id ORDER BY rating DESC", id=follow[0]["id"])
        view = session["follow"] # to view account name in list page
        following = []
        test1 = False # test condition for if user is in the follows database
        test2 = False # test condition for if user already follows the searched user in follows database

        for names in user:
            if session["user_id"] == names["user"]:
                following = db.execute("SELECT following FROM follows WHERE user=:user", user=session["user_id"])
                test1 = True

        if following:
            for name in following:
                if follow[0]["id"] == name["following"]:
                    test2 = True

        if not test2 or not test1:
            db.execute("INSERT INTO follows (user, following) VALUES (:user, :following)", user=session["user_id"], following=follow[0]["id"])

        return render_template("followlist.html", view=view, rows=rows)

    else:
        return render_template("follow.html")


@app.route("/followlist")
def followlist():

    return render_template("followlist.html")


@app.route("/myfeed", methods=["GET", "POST"])
def myfeed():
    """View feed of user activity for users following"""

    if request.method == "POST":

        view = request.form.get("viewList")

        user = db.execute("SELECT id FROM users WHERE username=:username", username=view)
        rows = db.execute("SELECT * FROM films WHERE id=:id ORDER BY rating DESC", id=user[0]["id"])

        return render_template("followlist.html", view=view, rows=rows)

    else:

        data = db.execute("SELECT id, title, rating, date FROM films WHERE NOT id=:id ORDER BY date DESC", id=session["user_id"])

        following = db.execute("SELECT following FROM follows WHERE user=:user", user=session["user_id"])

        items = [] # list of films and ratings for accounts the current logged in user is following

        for x in data:
            for user in following:
                if x["id"] == user["following"]:
                    items.append(x)

        for i in items:
            names = db.execute("SELECT username FROM users WHERE id=:id", id=i["id"])
            i["id"] = names[0]["username"] # swap id tags for the username of user following in the list to be rendered to the html page

        return render_template("myfeed.html", items=items)


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/login")


