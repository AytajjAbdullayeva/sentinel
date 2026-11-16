import { Navigate, Route, Routes } from "react-router-dom";
import { getToken } from "./api.js";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Scans from "./pages/Scans.jsx";
import Repos from "./pages/Repos.jsx";
import RepoDetail from "./pages/RepoDetail.jsx";
import ScanDetail from "./pages/ScanDetail.jsx";
import Simulate from "./pages/Simulate.jsx";
import Diff from "./pages/Diff.jsx";
import Monitor from "./pages/Monitor.jsx";
import About from "./pages/About.jsx";

function Guard({ children }) {
  return getToken() ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Guard>
            <Layout />
          </Guard>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="repos" element={<Repos />} />
        <Route path="repos/:id" element={<RepoDetail />} />
        <Route path="scans" element={<Scans />} />
        <Route path="scans/:id" element={<ScanDetail />} />
        <Route path="simulate" element={<Simulate />} />
        <Route path="ci-gate" element={<Diff />} />
        <Route path="monitoring" element={<Monitor />} />
        <Route path="about" element={<About />} />
      </Route>
    </Routes>
  );
}
