/**
 * AuthGuard — redirects to /login if no valid JWT is present.
 */

import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getToken, isTokenExpired } from "../utils/auth";

interface Props {
  children: React.ReactNode;
}

export function AuthGuard({ children }: Props) {
  const navigate = useNavigate();

  useEffect(() => {
    const token = getToken();
    if (!token || isTokenExpired(token)) {
      navigate("/login", { replace: true });
    }
  }, [navigate]);

  const token = getToken();
  if (!token || isTokenExpired(token)) return null;

  return <>{children}</>;
}
