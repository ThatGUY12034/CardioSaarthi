import { Routes, Route, Navigate } from "react-router-dom";
import Landing from "./pages/Landing";
import RoleSelection from "./pages/RoleSelection";
import Login from "./pages/Login";
import ProtectedRoute from "./components/ProtectedRoute";

import StudentDashboard from "./pages/student/StudentDashboard";
import PracticeCases from "./pages/student/PracticeCases";
import CasePractice from "./pages/student/CasePractice";
import CaseResult from "./pages/student/CaseResult";
import Progress from "./pages/student/Progress";
import Leaderboard from "./pages/student/Leaderboard";

import FacultyDashboard from "./pages/faculty/FacultyDashboard";
import StudentPerformance from "./pages/faculty/StudentPerformance";
import StudentProgress from "./pages/faculty/StudentProgress";
import ReviewQueue from "./pages/faculty/ReviewQueue";
import CaseApproval from "./pages/faculty/CaseApproval";

import PatientDashboard from "./pages/patient/PatientDashboard";
import UploadReport from "./pages/patient/UploadReport";
import ReportExplanation from "./pages/patient/ReportExplanation";
import Glossary from "./pages/patient/Glossary";

import AdminDashboard from "./pages/admin/AdminDashboard";
import ManageUsers from "./pages/admin/ManageUsers";
import ManageCases from "./pages/admin/ManageCases";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/choose-role" element={<RoleSelection />} />
      <Route path="/login/:role" element={<Login />} />

      {/* Student */}
      <Route element={<ProtectedRoute allowedRoles={["STUDENT"]} />}>
        <Route path="/student/dashboard" element={<StudentDashboard />} />
        <Route path="/student/cases" element={<PracticeCases />} />
        <Route path="/student/cases/:id" element={<CasePractice />} />
        <Route path="/student/cases/:id/result" element={<CaseResult />} />
        <Route path="/student/progress" element={<Progress />} />
        <Route path="/student/leaderboard" element={<Leaderboard />} />
      </Route>

      {/* Faculty */}
      <Route element={<ProtectedRoute allowedRoles={["FACULTY"]} />}>
        <Route path="/faculty/dashboard" element={<FacultyDashboard />} />
        <Route path="/faculty/students" element={<StudentPerformance />} />
        <Route path="/faculty/students/:id" element={<StudentProgress />} />
        <Route path="/faculty/review" element={<ReviewQueue />} />
        <Route path="/faculty/approvals" element={<CaseApproval />} />
      </Route>

      {/* Patient */}
      <Route element={<ProtectedRoute allowedRoles={["PATIENT"]} />}>
        <Route path="/patient/dashboard" element={<PatientDashboard />} />
        <Route path="/patient/upload" element={<UploadReport />} />
        <Route path="/patient/report/:id" element={<ReportExplanation />} />
        <Route path="/patient/glossary" element={<Glossary />} />
      </Route>

      {/* Admin */}
      <Route element={<ProtectedRoute allowedRoles={["ADMIN"]} />}>
        <Route path="/admin/dashboard" element={<AdminDashboard />} />
        <Route path="/admin/users" element={<ManageUsers />} />
        <Route path="/admin/cases" element={<ManageCases />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}