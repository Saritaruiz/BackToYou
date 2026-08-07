import json
import os
import uuid
import cgi
import shutil
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, quote
from http import cookies
from datetime import datetime


class UserRegistrationService:
    """Handles user registration and persistence for FR01."""

    def __init__(self, storagePath):
        self.StoragePath = storagePath
        self.Users = self.LoadUsers()

    def LoadUsers(self):
        """Load users from the JSON file if it exists."""
        if not self.StoragePath.exists():
            self.StoragePath.parent.mkdir(parents=True, exist_ok=True)
            self.StoragePath.write_text("[]", encoding="utf-8")
            return []

        try:
            with self.StoragePath.open("r", encoding="utf-8") as File:
                data = json.load(File)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, OSError):
            pass

        return []

    def SaveUsers(self):
        """Save the current users list to the JSON file."""
        with self.StoragePath.open("w", encoding="utf-8") as File:
            json.dump(self.Users, File, indent=2)
            File.write("\n")

    def RegisterUser(self, fullName, email, password):
        """Validate the input and create a new regular user if valid."""
        missingFields = []
        if not fullName.strip():
            missingFields.append("Full Name")
        if not email.strip():
            missingFields.append("Institutional Email")
        if not password.strip():
            missingFields.append("Password")

        if missingFields:
            return False, "Please complete the following fields: " + ", ".join(missingFields)

        if not email.endswith("@eafit.edu.co"):
            return False, "Please use an institutional email ending in @eafit.edu.co."

        for user in self.Users:
            if user.get("Email", "").lower() == email.lower():
                return False, "This email is already registered."

        newUser = {
            "FullName": fullName.strip(),
            "Email": email.strip(),
            "Password": password,
            "Role": "RegularUser",
        }
        self.Users.append(newUser)
        self.SaveUsers()
        return True, f"Registration successful for {fullName.strip()}."


class RegistrationHandler(BaseHTTPRequestHandler):
    """Serve the registration page and process form submissions."""

    def do_GET(self):
        """Serve pages for GET requests: registration, login, dashboard."""
        path = urlparse(self.path).path
        debugPath = Path(__file__).resolve().parent / "debug_routing.log"
        with debugPath.open("a", encoding="utf-8") as debugFile:
            debugFile.write(f"GET self.path={self.path} parsed={path}\n")
        print(f"DEBUG GET path={self.path} parsed={path}", flush=True)

        if path in ["/", "/index.html"]:
            self.SendHtml("", templateName="index.html")
            return

        if path == "/login":
            query = urlparse(self.path).query
            params = parse_qs(query)
            nextUrl = params.get("next", [""])[0]
            self.SendHtml("", templateName="login.html", replacements={"NextUrl": nextUrl})
            return

        # Serve uploaded files under /uploads/
        if path.startswith("/uploads/"):
            filePath = Path(__file__).resolve().parent / path.lstrip("/")
            if not filePath.exists() or not filePath.is_file():
                self.SendHtml("File not found.", statusCode=404)
                return
            mimeType, _ = mimetypes.guess_type(str(filePath))
            self.send_response(200)
            self.send_header("Content-Type", mimeType or "application/octet-stream")
            fs = filePath.stat()
            self.send_header("Content-Length", str(fs.st_size))
            self.end_headers()
            with filePath.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return

        if path == "/styles.css":
            filePath = Path(__file__).resolve().parent / "styles.css"
            if not filePath.exists() or not filePath.is_file():
                self.SendHtml("File not found.", statusCode=404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            fs = filePath.stat()
            self.send_header("Content-Length", str(fs.st_size))
            self.end_headers()
            with filePath.open("rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return

        if path == "/dashboard":
            sessionId = self.GetCookie("sessionid")
            session = SessionManager.GetSession(sessionId)
            if not session:
                # Not authenticated
                self.SendHtml("Please log in to access the dashboard.", messageType="error", templateName="login.html", statusCode=401)
                return

            # Build user's reports list
            reportService = ReportService(self.ReportsPath)
            reports = sorted(reportService.Reports, key=lambda r: r.get("CreatedAt", ""), reverse=True)

            if reports:
                items = []
                for r in reports:
                    title = r.get("Title", "(no title)")
                    rid = r.get("ReportId")
                    rtype = r.get("Type", "")
                    status = r.get("Status", "")
                    category = r.get("Category", "")
                    createdAt = r.get("CreatedAt", "")
                    creatorName = r.get("Creator", "Unknown")
                    eventDate = r.get("LostDate") or r.get("FoundDate") or ""
                    eventLocation = r.get("LostLocation") or r.get("FoundLocation") or ""
                    dateLabel = "Lost Date" if r.get("Type") == "Lost" else "Found Date"
                    imagePath = r.get("Image", "")
                    if imagePath:
                        imageTag = f"<div class='report-image-wrap'><img class='report-image' src='/{imagePath}' alt='report image'></div>"
                    else:
                        imageTag = ""
                    items.append(
                        f"<article class='report-card'>"
                        f"<div class='report-card-header'><div><strong>{title}</strong> · {rtype}</div><div class='report-meta'>{createdAt} · {creatorName}</div></div>"
                        f"{imageTag}"
                        f"<p>{r.get('Description', '')}</p>"
                        f"<div class='report-details'>Category: {category} · {dateLabel}: {eventDate} · Location: {eventLocation}</div>"
                        f"<div class='report-details'>Status: {status}</div>"
                        f"<div class='report-card-footer'><a href='/report?id={rid}'>View Details</a></div>"
                        f"</article>"
                    )
                reportsHtml = "<div class='feed'>" + "\n".join(items) + "</div>"
            else:
                reportsHtml = "<div class='empty-feed'>No reports found.</div>"

            # Render dashboard with replacements
            self.SendHtml("", templateName="dashboard.html", replacements={"FullName": session.get("FullName", ""), "Role": session.get("Role", ""), "ReportsHtml": reportsHtml})
            return

        # Create report page
        if path.startswith("/report/create"):
            sessionId = self.GetCookie("sessionid")
            session = SessionManager.GetSession(sessionId)
            if not session:
                query = urlparse(self.path).query
                fullUrl = "/report/create"
                if query:
                    fullUrl = f"/report/create?{query}"
                redirectUrl = f"/login?next={quote(fullUrl)}"
                self.SendRedirect(redirectUrl)
                return

            # Determine report type from query parameter (default Lost)
            query = urlparse(self.path).query
            params = parse_qs(query)
            reportType = params.get("type", ["Lost"])[0]
            dateLabel = "Lost Date" if reportType == "Lost" else "Found Date"
            actionName = f"Create {reportType} Item Report"

            # Show create report form with placeholders set
            self.SendHtml("", templateName="create_report.html", replacements={"Type": reportType, "DateLabel": dateLabel, "ActionName": actionName})
            return

        # View single report by id: /report?id=<id>
        if path == "/report":
            query = urlparse(self.path).query
            params = parse_qs(query)
            reportId = params.get("id", [None])[0]
            if not reportId:
                self.SendHtml("Report ID missing.", messageType="error", templateName="index.html", statusCode=400)
                return

            reportService = ReportService(self.ReportsPath)
            report = reportService.GetReportById(reportId)
            if not report:
                self.SendHtml("Report not found.", messageType="error", templateName="index.html", statusCode=404)
                return

            eventDate = report.get("LostDate") or report.get("FoundDate") or ""
            eventLocation = report.get("LostLocation") or report.get("FoundLocation") or ""
            dateLabel = "Lost Date" if report.get("Type") == "Lost" else "Found Date"
            imagePath = report.get("Image", "")
            if imagePath:
                imageTag = f"<p><img src='/{imagePath}' alt='report image' style='max-width:100%;border-radius:10px;'></p>"
            else:
                imageTag = ""

            self.SendHtml(
                "",
                templateName="report_view.html",
                replacements={
                    "Title": report.get("Title", "Report Details"),
                    "ReportId": report.get("ReportId", ""),
                    "Type": report.get("Type", ""),
                    "Status": report.get("Status", ""),
                    "Category": report.get("Category", ""),
                    "EventDate": eventDate,
                    "EventLocation": eventLocation,
                    "DateLabel": dateLabel,
                    "Creator": report.get("Creator", ""),
                    "Description": report.get("Description", ""),
                    "ImageTag": imageTag,
                },
            )
            return

        self.SendHtml("Page not found.", statusCode=404)

    def do_POST(self):
        """Process form submissions for registration and login."""
        path = urlparse(self.path).path
        contentType = self.headers.get("Content-Type", "")
        isMultipart = contentType.startswith("multipart/form-data")
        ContentLength = int(self.headers.get("Content-Length", "0"))
        Body = ""
        FormData = {}
        if not isMultipart:
            Body = self.rfile.read(ContentLength).decode("utf-8")
            FormData = parse_qs(Body, keep_blank_values=True)

        if path == "/register":
            FullName = FormData.get("fullName", [""])[0].strip()
            Email = FormData.get("institutionalEmail", [""])[0].strip()
            Password = FormData.get("password", [""])[0]

            Service = UserRegistrationService(self.StoragePath)
            Success, Message = Service.RegisterUser(FullName, Email, Password)

            if Success:
                self.SendHtml(Message, messageType="success", templateName="index.html")
            else:
                self.SendHtml(Message, messageType="error", templateName="index.html")
            return

        if path == "/login":
            # Validate required fields
            Email = FormData.get("institutionalEmail", [""])[0].strip()
            Password = FormData.get("password", [""])[0]
            NextUrl = FormData.get("next", [""])[0]

            missingFields = []
            if not Email:
                missingFields.append("Institutional Email")
            if not Password:
                missingFields.append("Password")

            if missingFields:
                msg = "Please complete the following fields: " + ", ".join(missingFields)
                self.SendHtml(msg, messageType="error", templateName="login.html", replacements={"NextUrl": NextUrl})
                return

            Service = UserRegistrationService(self.StoragePath)
            # Find user by email
            foundUser = None
            for user in Service.Users:
                if user.get("Email", "").lower() == Email.lower():
                    foundUser = user
                    break

            if not foundUser:
                self.SendHtml("Incorrect email or password.", messageType="error", templateName="login.html", replacements={"NextUrl": NextUrl})
                return

            # Check password (same method as registration: plain compare)
            if foundUser.get("Password") != Password:
                self.SendHtml("Incorrect email or password.", messageType="error", templateName="login.html", replacements={"NextUrl": NextUrl})
                return

            # Check active status (default True when missing)
            if foundUser.get("Active") is False:
                self.SendHtml("Account is inactive. Contact administrator.", messageType="error", templateName="login.html")
                return

            # Identify role and create session
            role = foundUser.get("Role", "RegularUser")
            sessionData = {"Email": foundUser.get("Email"), "FullName": foundUser.get("FullName", ""), "Role": role}
            sessionId = SessionManager.CreateSession(sessionData)

            # Set cookie and redirect to the intended page or dashboard
            headers = {"Set-Cookie": f"sessionid={sessionId}; HttpOnly; Path=/"}
            redirectTarget = NextUrl if NextUrl else "/dashboard"
            self.SendRedirect(redirectTarget, extraHeaders=headers)
            return

        if path == "/report/create":
            try:
                # Only authenticated users can create reports
                sessionId = self.GetCookie("sessionid")
                session = SessionManager.GetSession(sessionId)
                if not session:
                    self.SendHtml("Please log in to create reports.", messageType="error", templateName="login.html")
                    return

                # Handle multipart form when file upload is present
                contentType = self.headers.get('Content-Type', '')
                fileField = None
                Title = Description = Category = ItemDate = ItemLocation = ReportType = ""
                if contentType.startswith('multipart/form-data'):
                    print(f"DEBUG report/create contentType={contentType} length={ContentLength}", flush=True)
                    fs = cgi.FieldStorage(
                        fp=self.rfile,
                        headers=self.headers,
                        environ={
                            'REQUEST_METHOD': 'POST',
                            'CONTENT_TYPE': contentType,
                            'CONTENT_LENGTH': str(ContentLength),
                        },
                        keep_blank_values=True,
                    )
                    Title = fs.getvalue('title', '')
                    Description = fs.getvalue('description', '')
                    Category = fs.getvalue('category', '')
                    ItemDate = fs.getvalue('itemDate', '')
                    ItemLocation = fs.getvalue('itemLocation', '')
                    ReportType = fs.getvalue('type', 'Lost')
                    fileField = fs['itemImage'] if 'itemImage' in fs else None
                    print(f"DEBUG fileField type={type(fileField)} repr={repr(fileField)}", flush=True)
                else:
                    # fallback to urlencoded parsing
                    Title = FormData.get("title", [""])[0]
                    Description = FormData.get("description", [""])[0]
                    Category = FormData.get("category", [""])[0]
                    ItemDate = FormData.get("itemDate", [""])[0]
                    ItemLocation = FormData.get("itemLocation", [""])[0]
                    ReportType = FormData.get("type", ["Lost"])[0]

                # Validate required fields
                missingFields = []
                if not Title.strip():
                    missingFields.append("Report Title")
                if not Description.strip():
                    missingFields.append("Description")
                if not Category.strip():
                    missingFields.append("Category")
                if not ItemDate.strip():
                    missingFields.append("Date")
                if not ItemLocation.strip():
                    missingFields.append("Location")

                if missingFields:
                    msg = "Please complete the following fields: " + ", ".join(missingFields)
                    self.SendHtml(msg, messageType="error", templateName="create_report.html")
                    return

                # Validate date format (expecting YYYY-MM-DD)
                try:
                    parsedDate = datetime.fromisoformat(ItemDate)
                    ItemDateNormalized = parsedDate.date().isoformat()
                except ValueError:
                    self.SendHtml("Invalid date format. Use YYYY-MM-DD.", messageType="error", templateName="create_report.html")
                    return

                # If file uploaded, validate and save
                savedImagePath = ""
                if fileField is not None and getattr(fileField, 'filename', None):
                    filename = fileField.filename
                    allowed = {"jpg", "jpeg", "png"}
                    ext = Path(filename).suffix.lower().lstrip('.')
                    if ext not in allowed:
                        self.SendHtml("Unsupported image format. Allowed: JPG, JPEG, PNG.", messageType="error", templateName="create_report.html")
                        return

                    fileData = fileField.file.read()
                    maxSize = 5 * 1024 * 1024
                    if len(fileData) > maxSize:
                        self.SendHtml("Image exceeds maximum allowed size of 5 MB.", messageType="error", templateName="create_report.html")
                        return

                    uploadsDir = Path(__file__).resolve().parent / "uploads"
                    uploadsDir.mkdir(parents=True, exist_ok=True)
                    uniqueName = f"{uuid.uuid4()}.{ext}"
                    savePath = uploadsDir / uniqueName
                    with savePath.open('wb') as outFile:
                        outFile.write(fileData)
                    savedImagePath = f"uploads/{uniqueName}"

                reportService = ReportService(self.ReportsPath)
                creator = session.get("FullName") or session.get("Email")
                newReport = reportService.CreateReport(Title, Description, Category, ItemDateNormalized, ItemLocation, creator, reportType=ReportType, imagePath=savedImagePath)
                self.SendRedirect(f"/report?id={newReport.get('ReportId')}")
                return
            except Exception as e:
                print(f"ERROR processing /report/create: {e}", flush=True)
                self.SendHtml("An error occurred while creating the report. Please try again.", messageType="error", templateName="create_report.html")
                return

        # Unknown POST path
        self.SendHtml("Page not found.", statusCode=404)

    @property
    def ReportsPath(self):
        """Return the path to the reports JSON storage file."""
        return Path(__file__).resolve().parent / "data" / "reports.json"


        

    @property
    def StoragePath(self):
        """Return the path to the JSON storage file."""
        return Path(__file__).resolve().parent / "data" / "users.json"

    def SendHtml(self, message, messageType="info", statusCode=200, templateName="index.html", extraHeaders=None, replacements=None):
        """Render the given HTML template and inject a message placeholder.

        templateName: file name of the template in the project root.
        extraHeaders: optional dict of additional headers to send (e.g., Set-Cookie).
        """
        basePath = Path(__file__).resolve().parent / "base.html"
        childPath = Path(__file__).resolve().parent / templateName

        # Read base layout; if missing, fall back to child template directly
        if basePath.exists():
            baseContent = basePath.read_text(encoding="utf-8")
            childContent = ""
            if childPath.exists():
                childContent = childPath.read_text(encoding="utf-8")
            # Insert child into base
            content = baseContent.replace("{{BodyContent}}", childContent)
        else:
            # no base template, render child directly
            if childPath.exists():
                content = childPath.read_text(encoding="utf-8")
            else:
                content = ""

        # prepare message HTML
        if message:
            messageHtml = f"<div class='message {messageType}'>{message}</div>"
        else:
            messageHtml = ""

        # Inject message placeholder
        content = content.replace("{{Message}}", messageHtml)

        # apply template replacements if provided
        if replacements and isinstance(replacements, dict):
            for k, v in replacements.items():
                content = content.replace("{{" + k + "}}", str(v))

        # Set title if provided in replacements
        if replacements and "Title" in replacements:
            content = content.replace("{{Title}}", str(replacements.get("Title")))

        encodedContent = content.encode("utf-8")

        self.send_response(statusCode)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if extraHeaders:
            for k, v in extraHeaders.items():
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(encodedContent)))
        self.end_headers()
        self.wfile.write(encodedContent)

    def SendRedirect(self, location, statusCode=303, extraHeaders=None):
        """Send a redirect response with optional extra headers."""
        self.send_response(statusCode)
        if extraHeaders:
            for k, v in extraHeaders.items():
                self.send_header(k, v)
        self.send_header("Location", location)
        self.end_headers()

    def RenderReportView(self, report):
        eventDate = report.get("LostDate") or report.get("FoundDate") or ""
        eventLocation = report.get("LostLocation") or report.get("FoundLocation") or ""
        dateLabel = "Lost Date" if report.get("Type") == "Lost" else "Found Date"
        imagePath = report.get("Image", "")
        if imagePath:
            imageTag = f"<p><img src='/{imagePath}' alt='report image' style='max-width:100%;border-radius:10px;'></p>"
        else:
            imageTag = ""

        self.SendHtml(
            "",
            templateName="report_view.html",
            replacements={
                "Title": report.get("Title", "Report Details"),
                "ReportId": report.get("ReportId", ""),
                "Type": report.get("Type", ""),
                "Status": report.get("Status", ""),
                "Category": report.get("Category", ""),
                "EventDate": eventDate,
                "EventLocation": eventLocation,
                "DateLabel": dateLabel,
                "Creator": report.get("Creator", ""),
                "Description": report.get("Description", ""),
                "ImageTag": imageTag,
            },
        )

    def GetCookie(self, name):
        """Retrieve a cookie value by name from the request headers."""
        cookieHeader = self.headers.get("Cookie")
        if not cookieHeader:
            return None
        cookieJar = cookies.SimpleCookie()
        cookieJar.load(cookieHeader)
        morsel = cookieJar.get(name)
        if morsel:
            return morsel.value
        return None


class SessionManager:
    """Simple in-memory session manager using UUIDs stored in memory.

    This is intentionally minimal: sessions are not persisted and will
    be lost when the server restarts. It is sufficient for FR02.
    """
    Sessions = {}

    @classmethod
    def CreateSession(cls, data):
        sessionId = str(uuid.uuid4())
        cls.Sessions[sessionId] = data
        return sessionId

    @classmethod
    def GetSession(cls, sessionId):
        if not sessionId:
            return None
        return cls.Sessions.get(sessionId)


class ReportService:
    """Manage report persistence in JSON file similar to users service."""

    def __init__(self, storagePath):
        self.StoragePath = storagePath
        self.Reports = self.LoadReports()

    def LoadReports(self):
        if not self.StoragePath.exists():
            self.StoragePath.parent.mkdir(parents=True, exist_ok=True)
            self.StoragePath.write_text("[]", encoding="utf-8")
            return []

        try:
            with self.StoragePath.open("r", encoding="utf-8") as File:
                data = json.load(File)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, OSError):
            pass

        return []

    def SaveReports(self):
        with self.StoragePath.open("w", encoding="utf-8") as File:
            json.dump(self.Reports, File, indent=2)
            File.write("\n")

    def CreateReport(self, title, description, category, itemDate, itemLocation, creator, reportType="Lost", imagePath=""):
        """Create and persist a new report (Lost or Found).

        `reportType` must be either 'Lost' or 'Found'. The date and location
        fields are stored under keys that reflect the type to maintain
        backward compatibility with existing FR03 data.
        """
        reportId = str(uuid.uuid4())
        newReport = {
            "ReportId": reportId,
            "Title": title.strip(),
            "Description": description.strip(),
            "Category": category,
            "Type": reportType,
            "Status": "Pending",
            "Creator": creator,
            "CreatedAt": datetime.utcnow().isoformat(),
        }

        # Store date/location under type-specific keys to preserve FR03 format
        if reportType == "Found":
            newReport["FoundDate"] = itemDate
            newReport["FoundLocation"] = itemLocation.strip()
        else:
            newReport["LostDate"] = itemDate
            newReport["LostLocation"] = itemLocation.strip()

        # optional image path relative to project root
        if imagePath:
            newReport["Image"] = imagePath
        else:
            newReport["Image"] = ""

        self.Reports.append(newReport)
        self.SaveReports()
        return newReport

    def GetReportById(self, reportId):
        for r in self.Reports:
            if r.get("ReportId") == reportId:
                return r
        return None


def Main():
    """Start the web server."""
    serverAddress = ("127.0.0.1", 8000)
    httpd = ThreadingHTTPServer(serverAddress, RegistrationHandler)
    print("Server running at http://127.0.0.1:8000")
    httpd.serve_forever()


if __name__ == "__main__":
    Main()
