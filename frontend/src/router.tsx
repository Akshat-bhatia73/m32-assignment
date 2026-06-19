import { createBrowserRouter } from "react-router-dom"

import { ProtectedRoute } from "@/components/protected-route"
import { LoginPage } from "@/routes/login"
import { OverviewPage } from "@/routes/overview"
import { SignupPage } from "@/routes/signup"
import { WorkspacePage } from "@/routes/workspace"

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: "/", element: <WorkspacePage /> },
      { path: "/session/:sessionId", element: <WorkspacePage /> },
      { path: "/overview", element: <OverviewPage /> },
    ],
  },
])
