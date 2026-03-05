import { BrowserRouter } from "react-router-dom";
import AppRoutes from "./AppRoutes.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}