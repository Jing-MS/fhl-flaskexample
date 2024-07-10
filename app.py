from flask import (Flask, render_template, request)

app = Flask(__name__)

@app.route("/")
def get_chart():
    # Data to be passed to the template
    labels = ['January', 'February', 'March', 'April', 'May', 'June', 'July']
    data = [12, 6, 3, 5, 12, 13, 9]

    labels_jobcount = ['January', 'February', 'March', 'April', 'May', 'June', 'July']
    data_jobcount = [453, 416, 393, 512, 442, 413, 509]

    labels_token = ['January', 'February', 'March', 'April', 'May', 'June', 'July']
    data_token = [3089, 4160, 3933, 5120, 4472, 4133, 5091]

    jobs = [
    {"id": "1", "url": "https://example.com/job/1"},
    {"id": "2", "url": "https://example.com/job/2"},
    {"id": "3", "url": "https://example.com/job/3"},
    {"id": "4", "url": "https://example.com/job/4"},
    {"id": "5", "url": "https://example.com/job/5"},
    {"id": "6", "url": "https://example.com/job/6"},
    {"id": "7", "url": "https://example.com/job/7"},
    {"id": "8", "url": "https://example.com/job/8"},
    {"id": "9", "url": "https://example.com/job/9"},
    {"id": "10", "url": "https://example.com/job/10"}
  ]
    return render_template("index.html", {"request": request\
                  , "labels": labels, "data": data, "jobs": jobs\
                    , "labels_jobcount": labels_jobcount, "data_jobcount": data_jobcount\
                      , "labels_token": labels_token, "data_token": data_token})

# dummy change
if __name__ == '__main__':  
   app.run()