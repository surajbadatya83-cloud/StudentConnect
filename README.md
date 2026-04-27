# 🎓 StudentConnect

StudentConnect is a campus complaint management system built for students and administrators. It helps students report issues, support existing complaints through upvotes, and track progress updates, while giving admins a structured dashboard to review, manage, merge, and resolve complaints in one place.

## ✨ Overview

Many campus issues such as WiFi problems, broken infrastructure, lab equipment failures, or washroom concerns are reported repeatedly in scattered ways. StudentConnect brings these reports into a single platform where:

- Students can submit complaints with optional image proof
- Similar complaints can be detected before submission
- Community upvotes help highlight high-impact issues
- Admins can manage complaints with progress updates and moderation tools
- Notifications keep students informed about status changes

## 👥 Target Users

- Students
- Campus administrators
- Department coordinators
- Institution support teams

## 🛠 Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite, SQLAlchemy
- **Frontend:** HTML, CSS, Jinja2
- **Styling/UI:** Bootstrap 5
- **Authentication & Security:** Werkzeug password hashing, Flask sessions

## 🚀 Features

### Student Features

- User registration and login
- Complaint submission with category, department, priority, and image upload
- Smart duplicate complaint suggestions before posting
- Complaint feed with search, filters, and sorting
- Upvote system to support existing complaints
- Complaint detail view with progress and admin updates
- Comment and reply system
- Edit and delete own complaints
- Profile management
- Notifications for complaint updates

### Admin Features

- Dedicated admin dashboard
- Complaint review and moderation workflow
- Update complaint status and progress
- Merge duplicate complaints into one main issue
- Delete/archive complaints with reasons
- Deleted complaint log for transparency
- Complaint prioritization using vote counts

## 📂 Project Structure

```bash
Studentconnect/
├── app.py
├── static/
│   └── css/
│       ├── app-theme.css
│       ├── admin_dashboard.css
│       ├── dashboard.css
│       ├── login.css
│       ├── register.css
│       └── submit_complaint.css
├── templates/
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── submit_complaint.html
│   ├── complaint_detail.html
│   ├── my_complaints.html
│   ├── notifications.html
│   ├── profile.html
│   ├── settings.html
│   ├── admin_dashboard.html
│   ├── admin_complaints.html
│   ├── admin_complaint_detail.html
│   └── admin_deleted_complaints.html
├── uploads/
├── instance/
└── database/
```

## ⚙️ Installation

### Prerequisites

- Python 3.10+ recommended
- `pip`

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd Studentconnect
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

#### Windows

```bash
venv\Scripts\activate
```

#### macOS / Linux

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install flask flask-sqlalchemy sqlalchemy werkzeug
```

### 4. Configure environment variables

Set these optional environment variables before running the app:

```bash
SECRET_KEY=your-secret-key
DEFAULT_ADMIN_EMAIL=admin@example.com
```

Notes:

- `SECRET_KEY` is used for session security
- `DEFAULT_ADMIN_EMAIL` is the email that should receive the admin role
- To create an admin account, first register with the same email as `DEFAULT_ADMIN_EMAIL`

### 5. Run the application

```bash
python app.py
```

The app will start on:

```bash
http://127.0.0.1:5000
```

## 🧪 Usage

### For Students

1. Register a new account
2. Log in to the platform
3. Browse the complaint feed
4. Submit a new complaint if the issue does not already exist
5. Upvote similar complaints instead of creating duplicates
6. Track complaint progress and admin responses
7. Use comments to discuss or clarify issues
8. Check notifications for updates

### For Admins

1. Register using the email set in `DEFAULT_ADMIN_EMAIL`
2. Log in to access the admin dashboard
3. Review complaints based on votes, status, or category
4. Update progress and status
5. Merge duplicate complaints
6. Remove invalid complaints with a reason
7. Monitor deleted complaint history

## 🔄 Complaint Workflow

```text
Submitted → Under Review → In Progress → Resolved
```

## 🖼 Screenshots

Add screenshots here when available.

```md
![Home Page](path/to/homepage-screenshot.png)
![Student Dashboard](path/to/student-dashboard.png)
![Admin Dashboard](path/to/admin-dashboard.png)
![Submit Complaint](path/to/submit-complaint.png)
```

## 📌 Key Modules

- **Authentication:** Student registration, login, logout
- **Complaint Management:** Create, edit, delete, archive, merge
- **Voting System:** One vote per student per complaint
- **Comments:** Discussion threads with replies
- **Notifications:** Status and moderation alerts
- **Admin Tools:** Complaint moderation and duplicate handling

## 🔒 Security Notes

- Passwords are stored using hashed values
- Session-based authentication is used
- File uploads are restricted to image formats (`png`, `jpg`, `jpeg`)

## 🌱 Future Improvements

- Email notifications
- Role-based permission expansion
- Complaint analytics and reports
- Attachment size validation and drag-and-drop improvements
- Real-time updates with WebSockets
- REST API support for mobile integration
- Better settings persistence
- Deployment configuration for production

## 🤝 Contributing

Contributions are welcome. To contribute:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test the application
5. Submit a pull request

## 📄 License

This project is for educational or institutional use. Add your preferred license here if needed.

## 👤 Team Members

**[Suraj Badatya, Aayush Dubey]**

## 🙌 Final Note

StudentConnect is designed to make campus issue reporting more organized, transparent, and actionable. It gives students a stronger voice and helps admins respond with clearer priorities.
