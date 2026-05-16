Create a modern, minimal, and highly professional EdTech SaaS frontend application using React and Tailwind CSS. The app should have a sidebar navigation to switch between three main views: "Dashboard", "Cover Generator", and "Student 360".

Design Requirements:
- The UI must be clean, uncluttered, and enterprise-ready.
- Implement a built-in Dark/Light mode toggle switch. The color palette should adapt beautifully (e.g., slate/gray tones for dark mode, crisp white and very light grays for light mode, with a consistent primary brand color like indigo or violet).
- Use subtle shadows, rounded corners (xl or 2xl), and smooth hover transitions for interactive elements.
- The layout should feature a persistent left sidebar for navigation and a main content area on the right.

View 1: Dashboard (Overview & Analytics)
- A high-level overview of the system.
- Display summary cards (e.g., Total Exams Generated, Total Papers Scanned, Average System Score).
- A "Recent Scans" table displaying recent exam papers processed, with columns for Exam ID, Student ID, Date, and Status (Processing, Completed, Needs Review). Include color-coded status badges.
- Include placeholder charts (using simple Tailwind CSS bars or mock chart components) for "Overall Performance Trends".

View 2: Cover Generator
- A form to create a new exam cover template.
- Input fields: Course Code, Course Name, Instructor Name, and Total Question Count.
- A dynamic section to assign a "Topic" and "Max Points" to each question based on the Question Count.
- A prominent "Generate & Download PDF" button.
- A success state showing the generated "Exam ID" and a preview placeholder for the generated cover sheet.

View 3: Student 360 (Profile & Performance)
- Two-column layout within this view.
- Left Column: "Add Student" form (Student Number, Name, Email) and a searchable "Student Directory" list showing student names and total exams taken.
- Right Column: Display a placeholder if no student is selected. When selected, show a detailed Profile Header.
- Right Column -> Exam History: A clean table showing Course, Exam ID, Date, and Total Score.
- Right Column -> Performance by Topic: Custom horizontal progress bars using Tailwind utility classes displaying topic name, points earned vs max points, and percentage.

Technical Constraints:
- Use functional React components with Hooks (useState, useEffect).
- Implement basic state-based tab navigation (or React Router if preferred) to switch between the 3 views.
- Write extensive mock data (JSON format) within the components for all views (dashboard stats, recent scans, student directory, exam history, topic performance) so the entire application is fully functional, clickable, and interactive for a demo immediately, without needing a real backend connection.
- Ensure the layout is fully responsive (e.g., the sidebar collapses to a hamburger menu on mobile screens).