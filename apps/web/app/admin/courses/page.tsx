import TeacherCoursesPage from "../../teacher/courses/page";
import { AdminShell } from "../components/admin-shell";

export default function CoursesAdminPage() {
  return <AdminShell active="/admin/courses"><div className="admin-course-page"><TeacherCoursesPage /></div></AdminShell>;
}
