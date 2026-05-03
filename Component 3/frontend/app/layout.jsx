import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "../src/styles.css";

export const metadata = {
  title: "SL Social Media Risk Analysis",
  description: "Moderator demo UI for Sinhala harmful content analysis",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
