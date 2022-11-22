from datetime import datetime
from flask import Flask, redirect, render_template, request, session
from flask_session import Session
from functools import wraps
import os
from PIL import Image
import sqlite3

# Set upload folder for user avatars, and only allow certain extensions
UPLOAD_FOLDER = 'static/img/user'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Configuration for the app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 1 * 1000 * 1000

# Template auto reload
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Use filesystem for session instead of cookies
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# When the user tries to upload a file that is too large, display a custom error page
@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template("error.html", message="The file you are trying to upload is too large. Max file size is 1 mb.", back="/create_group")


# Make sure the user does not upload any forbidden files (https://flask.palletsprojects.com/en/2.2.x/patterns/fileuploads/)
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Calculate percentages for placements in the results
def calculate_percent(list):
    data = []
    # For every result
    for item in list:
        # Calculate the percentage
        percentage = round(((item / sum(list)) * 100), 1)
        # Append to the list
        data.append(percentage)

    return data


# Enable functionality to require login on certain pages
def login_required(f):
    # As per https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/select_group")
        return f(*args, **kwargs)

    return decorated_function


# Calculate points depending on placement:
def calculate_points(place):
    # If placed from 3rd to 12th, subtracting place from 13 results in the correct points given
    if place in range(3, 13):
        points = 13 - place
    # If placed 2nd or 1st, more points are given.
    elif place == 2:
        points = 12
    elif place == 1:
        points = 15
    else:
        points = 0

    return points


# The function that looks up the data depending on what you need. Returns a list of query results.
# Accepted arguments are: "group", "racers", "cups", "courses" and "results".
def lookup(*args):
    connection = sqlite3.connect('static/stats.db')
    cursor = connection.cursor()

    results = []
    if "group" in args:
        group = cursor.execute("SELECT * FROM groups WHERE id = ?", ([str(session["user_id"])]))
        group = cursor.fetchall()
        results.append(group)
    if "racers" in args:
        racers = cursor.execute("SELECT * FROM racers WHERE group_id = ?", ([str(session["user_id"])]))
        racers = cursor.fetchall()
        results.append(racers)
    if "cups" in args:
        cups = cursor.execute("SELECT * FROM cups")
        cups = cursor.fetchall()
        results.append(cups)
    if "courses" in args:
        courses = cursor.execute("SELECT * FROM courses")
        courses = cursor.fetchall()
        results.append(courses)
    if "results" in args:
        result = cursor.execute("SELECT * FROM results WHERE group_id = ?", ([str(session["user_id"])]))
        result = cursor.fetchall()
        results.append(result)

    connection.close()

    return results


# Lookup racer ID and name, and make a list connecting the two
def racer_lookup(group_data, racer_count):
    data = []
    connection = sqlite3.connect('static/stats.db')
    cursor = connection.cursor()

    for i in range(racer_count):
        # The ID for raceres begins at group_data[3] and continues for as many racers as there are in the group
        racer = group_data[i + 3]
        # Lookup the name of the racer by their ID
        name = cursor.execute("SELECT name FROM racers WHERE id = ?", ([group_data[i + 3]]))
        name = cursor.fetchall()
        # Append the data
        data.append([racer, name[0][0]])

    connection.close()

    return data


# The index page
@app.route("/", methods=["GET"])
def index():

    # If a group is logged in
    if session:
        # Use the lookup function to lookup groups and racers to display
        data = lookup("group", "racers")
        return render_template("index.html", group=data[0], racers=data[1])
    else:
        return render_template("index.html")


# The page to create a group
@app.route("/create_group", methods=["GET", "POST"])
def create_group():
    if request.method == "GET":
        return render_template("create_group.html")

    else:
        # Set the point to go back to
        back = "/create_group"
        # Do some safety checks. The user has to at least provide the name of the group and the two first racers
        if not request.form.get("group_name") or not request.form.get("racer_one") or not request.form.get("racer_two"):
            return render_template("error.html", message="Please enter a group name and at least two racers.", back=back)

        # The user must not provide a fourth racer when no third racer is provided
        if request.form.get("racer_four") and not request.form.get("racer_three"):
            return render_template("error.html", message="Please enter the racers in order.", back=back)

        # Find out how many racers the user is trying to register
        racer_count = 0
        if request.form.get("racer_one"):
            racer_count = racer_count + 1
        if request.form.get("racer_two"):
            racer_count = racer_count + 1
            if request.form.get("racer_two") == request.form.get("racer_one"):
                return render_template("error.html", message="Racers in the same group can't have the same name.", back=back)
        if request.form.get("racer_three"):
            racer_count = racer_count + 1
            if request.form.get("racer_three") in (request.form.get("racer_one"), request.form.get("racer_two")):
                return render_template("error.html", message="Racers in the same group can't have the same name.", back=back)
        if request.form.get("racer_four"):
            racer_count = racer_count + 1
            if request.form.get("racer_four") in (request.form.get("racer_one"), request.form.get("racer_two"), request.form.get("racer_three")):
                return render_template("error.html", message="Racers in the same group can't have the same name.", back=back)

        # Set a list to fill
        file = [None]*racer_count

        # Request the users avatar uploads
        for i in range(racer_count):
            file[i] = request.files['file_' + str(i)]

        # Open SQL connection
        connection = sqlite3.connect('static/stats.db')
        cursor = connection.cursor()

        # First, just create the group name and thus be provided an ID
        cursor.execute("INSERT INTO groups (name, racers) VALUES (?, ?)", (request.form.get("group_name"), racer_count))

        # Look up the ID just provided
        group_id = cursor.execute("SELECT id FROM groups WHERE name == ?", ([request.form.get("group_name")]))
        group_id = cursor.fetchall()

        # Set up some variables and lists to use
        racer = ["racer_one", "racer_two"]
        if racer_count > 2:
            racer.append("racer_three")
        if racer_count > 3:
            racer.append("racer_four")
        racer_id = ["racer_id_one", "racer_id_two"]
        if racer_count > 2:
            racer_id.append("racer_id_three")
        if racer_count > 3:
            racer_id.append("racer_id_four")

        # Loop through the number of racers and save their avatars as well as their information
        for i in range(racer_count):
            # Save the default avatar string for this user and use that to create the initial user entry
            default = "default/default_" + str(i) + ".jpg"
            cursor.execute("INSERT INTO racers (name, group_id, avatar) VALUES (?, ?, ?)",
                           (request.form.get(racer[i]), group_id[0][0], default))
            id = cursor.execute("SELECT id FROM racers WHERE group_id = ? AND name = ?",
                                (group_id[0][0], request.form.get(racer[i])))
            id = cursor.fetchall()

            # If the user specified a file but it does not match the allowed file types, show an error
            if file[i] and not allowed_file(file[i].filename):
                return render_template("error.html", message="This file type is not allowed. Allowed file types: png, jpg, jpeg, gif.", back="/create_group")
            # If the user specified a file and the file type is allowed, organize the file
            elif file[i] and allowed_file(file[i].filename):
                # Create the new file name
                f_name = "user_" + str(id[0][0])
                # Get the extension of the original file
                extension = os.path.splitext(file[i].filename)
                # Save the new file name by combining the name with the extension
                file[i].filename = f_name + extension[1]
                # save the location plus file name as a string
                location = "static/img/avatars/" + str(file[i].filename)
                # Save the initial file
                file[i].save(location)
                # Resize the file
                temp = Image.open(location)
                avatar = temp.resize((480, 480))
                # Save the file
                avatar.save(location)
                # Create the string to update the racers entry
                string = "UPDATE racers SET avatar = '" + file[i].filename + "' WHERE id = ?"
                # Save the avatar to the database
                cursor.execute(string, ([str(id[0][0])]))

            # Update the group with the racers ID
            string = "UPDATE groups SET " + racer_id[i] + " = ? WHERE id = ?"
            cursor.execute(string, (id[0][0], group_id[0][0]))

        # Commit SQL and close
        connection.commit()
        connection.close()

        return redirect("/")


# The page to select a group, somewhat of a login page but with no password
@app.route("/select_group", methods=["GET", "POST"])
def select_group():

    if request.method == "GET":
        # Set the return point
        back = "/select_group"

        # Open the SQL connection
        connection = sqlite3.connect('static/stats.db')
        cursor = connection.cursor()

        # Get all groups
        groups = cursor.execute("SELECT id, name FROM groups")
        groups = cursor.fetchall()

        # Close the SQL connection
        connection.close()

        if groups == []:
            return render_template("error.html", message="There are no groups. Create a group first.", back=back)
        else:
            return render_template("select_group.html", groups=groups)

    else:
        # Get the group id from the html
        group_id = request.form.get("group_id")
        # Login the group
        session["user_id"] = int(group_id)
        return redirect("/")


# Logout the group
@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")


# Add a race result to the database
@app.route("/add_result", methods=["GET", "POST"])
@login_required
def add_result():

    if request.method == "GET":

        # Use the lookup function to look up group, racers, cups and courses
        data = lookup("group", "racers", "cups", "courses")

        # Check datetime to use for default setting in the html
        time = datetime.today().strftime('%Y-%m-%d')

        return render_template("add_result.html", group=data[0], racers=data[1], cups=data[2], courses=data[3], count=data[0][0][2], time=time)

    else:
        # Set the point to go back to
        back = "/add_result"

        # Use the lookup function to look up the group
        data = lookup("group")

        # See how many racers there are
        racer_count = data[0][0][2]

        results = []
        # Get the results for each racer from the html and append them to the results list
        for i in range(racer_count):
            racer_id = request.form.get("id_" + str(i))
            result = request.form.get("results_" + str(racer_id))
            temp = {"racer_id": racer_id, "place": result}
            results.append(temp)
        # Add some empty dictionaries for each missing racer in a group
        if racer_count == 2:
            temp1 = {"racer_id": 0, "place": 0}
            temp2 = temp1
            results.append(temp1)
            results.append(temp2)
        if racer_count == 3:
            temp = {"racer_id": 0, "place": 0}
            results.append(temp)

        # Make sure that two racers do not have the same placement
        if not results[i]["place"] == 0:
            for i in range(racer_count):
                for j in range(racer_count):
                    if j == i:
                        continue
                    if results[i]["place"] == results[j]["place"]:
                        return render_template("error.html", message="Two racers can't have the same result.", back=back)

        # Make sure all other data is submitted
        if not request.form.get("date"):
            return render_template("error.html", message="Please select the date.", back=back)
        if not request.form.get("course_select"):
            return render_template("error.html", message="Please select the course.", back=back)

        date = request.form.get("date")
        course = request.form.get("course_select")

        # Enter the results into the database
        connection = sqlite3.connect('static/stats.db')
        cursor = connection.cursor()
        cursor.execute("INSERT INTO results (datetime, course_id, group_id, racer_one_result, racer_two_result, racer_three_result, racer_four_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (date, course, data[0][0][0], results[0]["place"], results[1]["place"], results[2]["place"], results[3]["place"]))
        connection.commit()
        connection.close()

        return redirect("/add_result")


# Show the stats for an individual racer
@app.route("/racer_stats", methods=["POST"])
@login_required
def racer_stats():

    # Set point to go back to
    back = "/"

    # Get racer ID from html document
    racer_id = int(request.form.get("racer_id"))

    # Use lookup function to lookup group and results
    data = lookup("group", "results")
    group_data = data[0]
    results = data[1]

    # Set the number of racers in the group
    racer_count = group_data[0][2]

    # If there are no results, then no results have been recorded.
    if not results:
        return render_template("error.html", message="No results have been recorded.", back=back)

    # Idenfity IDs of each racer in the group and store them in the variables
    racer = [0]*racer_count
    for i in range(racer_count):
        racer[i] = group_data[0][i + 3]
    racer_no = 0
    # Check which one corresponds with the ID we are looking up and save the racer_no (Their numbers in the group are different from their ID)
    for i in range(3, 7):
        if group_data[0][i] == racer_id:
            racer_no = (i - 2)
            break

    # Open SQL to do some queries
    connection = sqlite3.connect('static/stats.db')
    cursor = connection.cursor()

    target_racer = cursor.execute("SELECT name, avatar FROM racers WHERE group_id = ? and id = ?",
                                  (group_data[0][0], str(racer_id)))
    target_racer = cursor.fetchall()

    # Set up some variables and lists to use in the loop

    # The racer we want to look at
    subject = racer_no + 3
    # The list of placements
    place_list = [0]*12
    # The racers place in the group
    group_place = 0
    group_place_list = [0]*racer_count
    # The list of results
    result_list = []
    # The list of courses
    course_list = [0]*97

    # Take the results and look through them and save the data
    for result in results:

        # Save the date and the course ID
        date = result[1]
        course = result[2]

        # Check the english and Japanese names of the course from the ID
        course_name = cursor.execute("SELECT en_name, jp_name FROM courses WHERE id = ?", ([str(course)]))
        course_name = cursor.fetchall()

        # Check which place the racer we are looking at had in the race
        place = result[subject]

        # If the place is 1, that means the racer won that race, add 1 to the course list to figure out the racers best course
        if place == 1:
            course_list[course] = course_list[course] + 1

        # Add the value to the list to see how often what place was achieved
        place_list[place - 1] = place_list[place - 1] + 1

        # Save group results one racer at a time

        order = {racer[0]: result[4], racer[1]: result[5]}
        if racer_count > 2:
            order[racer[2]] = result[6]
        if racer_count > 3:
            order[racer[3]] = result[7]

        # Sort group results to find out the place in the group
        order = sorted(order.items(), key=lambda key_value: key_value[1])

        # Check each result for which place the current racer got, and save variables accordingly.
        for i in range(racer_count):
            if order[i][0] == racer_id:
                group_place = (i)
        group_place_list[group_place] = group_place_list[group_place] + 1

        # Save date, course id, course names in en and jp, the place and group place in a dictionary.
        result = {"date": date, "course_id": course,
                  "course_en": course_name[0][0], "course_jp": course_name[0][1], "place": place, "group_place": group_place }
        # Append the dictionary to the list
        result_list.append(result)

    # Create percentage of race placement
    percentage_list = calculate_percent(place_list)
    # Create percentage of race placement within group
    group_percentage_list = calculate_percent(group_place_list)

    # Create a list of best courses
    best_courses = []
    # Check which course the racer has won the most races
    check = max(course_list)
    # If there are no wins or just one win, that means there is no best course yet. In that case, append 0.
    if check == 0 or check == 1:
        best = 0
        best_courses.append(best)
    else:
        # Otherwise find all courses that share the highest amount of wins (that are at least 2 wins)
        best = [i for i, x in enumerate(course_list) if x == check]

        # Look up the courses and append them to the list
        for i in best:
            temp = cursor.execute("SELECT en_name, jp_name FROM courses WHERE id = ?", ([str(i)]))
            temp = cursor.fetchall()
            temp_list = [i, temp[0][0], temp[0][1]]
            best_courses.append(temp_list)

    # Close the SQL connection
    connection.close()

    return render_template("racer_stats.html", places=place_list, percentages=percentage_list, group_places=group_place_list, group_percentages=group_percentage_list, best=best_courses, racer=target_racer, group=group_data[0][1], races=len(results), count=racer_count)


# Show the stats for the whole group
@app.route("/group_stats", methods=["GET"])
@login_required
def group_stats():

    back = "/"
    # Get data on group, racers and results
    data = lookup("group", "results")
    group_data = data[0]
    racer_count = group_data[0][2]
    results = data[1]

    if not results:
        return render_template("error.html", message="No results have been recorded.", back=back)

    # Save racer id to use
    racers = racer_lookup(group_data[0], racer_count)

    # Prepare points list to add points for each placement: racer_id: points
    points = {}
    for i in range(racer_count):
        points[racers[i][0]] = 0

    # Wins stores the total wins for each racer
    wins = []

    # Store all results for this group so far
    results_list = []

    # Create a list that has an entry for each racer with a sublist for each placement within a group
    per_racer = [[0]*racer_count for x in range(racer_count)]

    # Create a list that has an entry for each racer with a sublist for each placement within a race
    places_list = [[0]*12 for x in range(racer_count)]

    # Iterate over results and get necessary data
    for result in results:
        # Lookup the name of the current course
        connection = sqlite3.connect('static/stats.db')
        cursor = connection.cursor()
        course_name = cursor.execute("SELECT en_name, jp_name FROM courses WHERE id = ?", ([str(result[2])]))
        course_name = cursor.fetchall()

        order = {}
        for i in range(racer_count):
            # Calculate points to figure out rank
            points[racers[i][0]] = points[racers[i][0]] + calculate_points(int(result[i + 4]))
            # Order the results to see who was which place in the group
            order[racers[i][0]] = result[i + 4]
            # Enter the results in the general list of race wins per racer
            places_list[i][result[i + 4] - 1] = places_list[i][result[i + 4] - 1] + 1

        g_order = order.copy()
        for i in range(racer_count):
            # Replace the ID of the racer with the number within the group
            g_order[i + 1] = g_order.pop(racers[i][0])

         # Sort the results list
        order = sorted(order.items(), key=lambda key_value: key_value[1])
        # Sort the group results list
        g_order = sorted(g_order.items(), key=lambda key_value: key_value[1])
        # Save results per race
        rank = {}
        for i in range(racer_count):
            rank[i + 1] = g_order[i][0]
        # Enter the results in the general list of group wins per racer
        for i in range(racer_count):
            per_racer[rank[i + 1] - 1][i] = per_racer[rank[i + 1] - 1][i] + 1
        wins.append(rank)

        # Create a dictionary to use with the important information
        data = {"date": result[1], "course_id": result[2], "course_en": course_name[0][0], "course_jp": course_name[0][1],
                "1st_id": order[0][0], "1st_place": order[0][1], "2nd_id": order[1][0], "2nd_place": order[1][1]}

        # If there are more than 2 racers, first add the third racer
        if racer_count > 2:
            data["3rd_id"] = order[2][0]
            data["3rd_place"] = order[2][1]
        # If there are more than 3 racers, add the fourth racer
        if racer_count > 3:
            data["4th_id"] = order[3][0]
            data["4th_place"] = order[3][1]

        results_list.append(data)

    # Order the list of points so the person with the most is 1, etc.
    ordered_points = sorted(points.items(), key=lambda key_value: key_value[1], reverse=True)
    ordered_list = []
    place = 0

    # Create the points list
    for entry in ordered_points:
        place = place + 1
        data = cursor.execute("SELECT name, avatar, id FROM racers WHERE id = ?", ([str(entry[0])]))
        data = cursor.fetchall()
        temp = {"id": data[0][2], "name": data[0][0], "avatar": data[0][1], "points": entry[1], "place": place}
        ordered_list.append(temp)

    # Calculate percentages of group placements
    group_percentage = []
    for i in range(racer_count):
        temp = calculate_percent(per_racer[i])
        group_percentage.append(temp)

    # Calculate percentages of race placements
    place_percentage = []
    for i in range(racer_count):
        temp = calculate_percent(places_list[i])
        place_percentage.append(temp)

    # Make a name dictionary for easier display in HTML
    names = {}
    for i in range(racer_count):
        names[racers[i][0]] = racers[i][1]

    connection.close()
    return render_template("group_stats.html", group=group_data, races=len(results), rank=ordered_list, g_place=per_racer, g_pct=group_percentage, a_place=places_list, a_pct=place_percentage, results=results_list, names=names, count=racer_count)


# Show the stats for a course
@app.route("/course_stats", methods=["GET", "POST"])
@login_required
def course_stats():
    if request.method == "GET":

        # Set the point to go back to
        back = "/"

        # Call the lookup function to lookup data
        data = lookup("cups", "courses", "results")

        if not data[2]:
            return render_template("error.html", message="No results have been recorded.", back=back)

        return render_template("course_select.html", cups=data[0], courses=data[1])
    else:

        # Set the point to go back to
        back = "/course_stats"

        # Get course id from HTML
        course_id = request.form.get("course_select")

        # Open SQL and query a bunch of data to use. Since this data is different, we are not using the lookup function
        connection = sqlite3.connect('static/stats.db')
        cursor = connection.cursor()

        # Group data
        group_data = cursor.execute(
            "SELECT id, name, racers, racer_id_one, racer_id_two, racer_id_three, racer_id_four FROM groups WHERE id = ?", ([str(session["user_id"])]))
        group_data = cursor.fetchall()

        # All results for that group with that course ID
        results = cursor.execute(
            "SELECT datetime, racer_one_result, racer_two_result, racer_three_result, racer_four_result FROM results WHERE group_id = ? AND course_id =? ORDER BY id", (str(group_data[0][0]), course_id))
        results = cursor.fetchall()

        if not results:
            return render_template("error.html", message="No records for this course yet.", back=back)

        # Check the name and cup id for that course
        course = cursor.execute("SELECT id, cup_id, en_name, jp_name FROM courses WHERE id = ?", ([str(course_id)]))
        course = cursor.fetchall()

        # Check the cup for that course
        cup = cursor.execute("SELECT id, en_name, jp_name FROM cups WHERE id = ?", ([str(course[0][1])]))
        cup = cursor.fetchall()

        # Check how many races there were in total, including this course
        total = cursor.execute("SELECT COUNT(id) FROM results WHERE group_id = ?", ([str(group_data[0][0])]))
        total = cursor.fetchall()

        # The length of the results gives us the amount of races
        times = len(results)
        # Get the percentage for this course compared to all races
        percent = round((times / total[0][0] * 100), 1)
        # Save the amount of racers for this group
        racer_count = group_data[0][2]

        # Look up all racers names
        names_list = racer_lookup(group_data[0], racer_count)

        races = []
        names = {}
        wins = {}
        # create names list and wins list
        for i in range(racer_count):
            names[names_list[i][0]] = names_list[i][1]
            wins[names_list[i][0]] = 0

        # Make a dictionary of the placements for each racer for that course
        for result in results:
            order = {}
            for i in range(racer_count):
                order[names_list[i][0]] = result[i + 1]
            # Order the list and count the wins for that racer
            order = sorted(order.items(), key=lambda key_value: key_value[1])
            wins[order[0][0]] = wins[order[0][0]] + 1

            # Create a dictionary for each race to show date and winner
            race = {"date": result[0], "winner": names[order[0][0]]}
            races.append(race)

        # Create empty list to store racers with 0 wins on that course
        toremove = []
        # For all keys in the wins dictionary, if any racer has 0 wins, store them in the toremove list
        for key, value in wins.items():
            if value == 0:
                toremove.append(key)

        # Remove all entries from the dictionary that have keys stored in the toremove list, thus erasing 0 win racers
        for item in toremove:
            del wins[item]

        # Sort the dictionary of remaining racers
        dict(sorted(wins.items(), key=lambda item: item[1]))

        # The first item is the number of the racer with the most wins
        most = next(iter(wins))

        # Check the name of the racer by entering the number as key
        name = names[most]

        return render_template("course_stats.html", course=course, cup=cup, times=times, percent=percent, most=name, races=races)


# Show the stats per race date
@app.route("/daily_stats", methods=["GET"])
@login_required
def daily_stats():

    # Set the point to go back to
    back = "/"

    # Open SQL
    connection = sqlite3.connect('static/stats.db')
    cursor = connection.cursor()

    # Select datetimes so the results can be sorted into them
    dates = cursor.execute("SELECT DISTINCT datetime FROM results WHERE group_id = ? ORDER BY datetime DESC",
                           ([str(session["user_id"])]))
    dates = cursor.fetchall()

    group_data = cursor.execute(
        "SELECT id, name, racers, racer_id_one, racer_id_two, racer_id_three, racer_id_four FROM groups WHERE id = ?", ([str(session["user_id"])]))
    group_data = cursor.fetchall()
    racer_count = group_data[0][2]

    names_list = racer_lookup(group_data[0], racer_count)
    names = {}
    # create names list and wins list
    for i in range(racer_count):
        names[names_list[i][0]] = names_list[i][1]

    if not dates:
        return render_template("error.html", message="No results have been recorded.", back=back)

    blocks = []

    # For each date, select all the races for that date
    for i in range(len(dates)):
        temp = cursor.execute("SELECT datetime, course_id, racer_one_result, racer_two_result, racer_three_result, racer_four_result FROM results WHERE group_id = ? AND datetime = ? ORDER BY id DESC",
                              (str(session["user_id"]), str(dates[i][0])))
        temp = cursor.fetchall()

        inner_block = []
        for entry in temp:
            course_name = cursor.execute("SELECT en_name, jp_name, id FROM courses WHERE id = ?", ([str(entry[1])]))
            course_name = cursor.fetchall()
            order = {}
            for i in range(racer_count):
                order[names_list[i][0]] = entry[i + 2]
            order = sorted(order.items(), key=lambda key_value: key_value[1])
            block = {"course_id": course_name[0][2], "en_name": course_name[0][0], "jp_name": course_name[0][1],
                     "1st_name": names[order[0][0]], "1st_place": order[0][1], "2nd_name": names[order[1][0]], "2nd_place": order[1][1]}
            if racer_count > 2:
                block["3rd_name"] = names[order[2][0]]
                block["3rd_place"] = order[2][1]
            if racer_count > 3:
                block["4th_name"] = names[order[3][0]]
                block["4th_place"] = order[3][1]
            inner_block.append(block)

        blocks.append(inner_block)
    connection.close()

    return render_template("daily_stats.html", dates=dates, blocks=blocks, count=racer_count)


# Show the data entries
@app.route("/data", methods=["GET", "POST"])
@login_required
def data():
    if request.method == "GET":

        # Set the point to go back to
        back = "/"

        # Lookup the results
        query = lookup("results")
        results = query[0]

        # If there are no results, tell the user as such
        if not results:
            return render_template("error.html", message="No results have been recorded.", back=back)

        connection = sqlite3.connect('static/stats.db')
        cursor = connection.cursor()

        data = []

        # For all results
        for entry in results:
            # Check the english name for the course
            course_name = cursor.execute("SELECT en_name FROM courses WHERE id = ?", ([entry[2]]))
            course_name = cursor.fetchall()

            # Add date, course name and id to temp, to be used in the HTML
            temp = [entry[1], course_name[0][0], entry[0]]
            data.append(temp)

        connection.close()
        return render_template("data.html", data=data)

    else:

        # Get the ID for the datapoint the user wishes to erase
        entry = request.form.get("erase_data")

        # Open SQL
        connection = sqlite3.connect('static/stats.db')
        cursor = connection.cursor()

        # Delete the entry
        cursor.execute("DELETE FROM results WHERE id = ?", ([str(entry)]))

        connection.commit()
        connection.close()

        return redirect("/data")


# Allows the user to edit their group details
@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    if request.method == "GET":
        data = lookup("group", "racers")
        group_name = data[0][0][1]
        racers = data[1]
        return render_template("edit.html", group_name=group_name, racers=racers)

    else:

        data = lookup("racers")
        racer = data[0]
        connection = sqlite3.connect('static/stats.db')
        cursor = connection.cursor()

        if request.form.get("group_name"):
            cursor.execute("UPDATE groups SET name = ? WHERE id = ?", (request.form.get("group_name"), str(session["user_id"])))
        for i in range(len(racer)):
            if request.form.get("racer_" + str(racer[i][0])):
                cursor.execute("UPDATE racers SET name = ? WHERE id = ?",
                               (request.form.get("racer_" + str(racer[i][0])), str(racer[i][0])))
            if request.files['file_' + str(racer[i][0])]:
                file = request.files['file_' + str(racer[i][0])]

                if file and not allowed_file(file.filename):
                    return render_template("error.html", message="This file type is not allowed. Allowed file types: png, jpg, jpeg, gif.", back="/create_group")
                # If the user specified a file and the file type is allowed, organize the file
                elif file and allowed_file(file.filename):
                    # Erase the old file:
                    if racer[i][3] not in ("default/default_1.jpg", "default/default_2.jpg", "default/default_3.jpg", "default/default_4.jpg"):
                        old_avatar = "static/img/avatars/" + str(racer[i][3])
                        os.remove(old_avatar)
                    # Create the new file name
                    f_name = "user_" + str(racer[i][0])
                    # Get the extension of the original file
                    extension = os.path.splitext(file.filename)
                    # Save the new file name by combining the name with the extension
                    file.filename = f_name + extension[1]
                    # save the location plus file name as a string
                    location = "static/img/avatars/" + str(file.filename)
                    # Save the initial file
                    file.save(location)
                    # Resize the file
                    temp = Image.open(location)
                    avatar = temp.resize((480, 480))
                    # Save the file
                    avatar.save(location)
                    # Create the string to update the racers entry
                    string = "UPDATE racers SET avatar = '" + file.filename + "' WHERE id = ?"
                    # Save the avatar to the database
                    cursor.execute(string, [str(racer[i][0])])

        connection.commit()
        connection.close()

        return redirect("/")