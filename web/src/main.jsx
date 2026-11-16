import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
// GitLab (Pajamas) themed UI: Bootstrap 4 grid utilities + Material Icons, restyled by gitlab.css.
import "bootstrap/dist/css/bootstrap.min.css";
import "material-icons/iconfont/material-icons.css";
import App from "./App.jsx";
import "./gitlab.css"; // GitLab-clone theme + chrome (super-sidebar, command palette)

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
