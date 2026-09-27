import { createContext, useContext, useState, useEffect } from "react";
import axiosClient from "../api/axiosClient";

const AuthContext = createContext(null);

// Normalize role from URL (lowercase) to internal (uppercase)
const normalizeRole = (role) => {
  const r = String(role || "").toLowerCase();
  if (r === "student") return "STUDENT";
  if (r === "faculty") return "FACULTY";
  if (r === "patient") return "PATIENT";
  if (r === "admin") return "ADMIN";
  return "STUDENT";
};

const demoUsers = {
  STUDENT: {
    id: 101,
    name: "Saniya Mankar",
    role: "STUDENT",
    email: "saniya@terna.edu",
    collegeId: "TE18/2023/C5001",
  },
  FACULTY: {
    id: 201,
    name: "Dr. Sharma",
    role: "FACULTY",
    email: "sharma@terna.edu",
    collegeId: "TE18/FAC/C001",
  },
  PATIENT: {
    id: 301,
    name: "Ramesh Kumar",
    role: "PATIENT",
    email: "ramesh@example.com",
    collegeId: "PT001",
  },
  ADMIN: {
    id: 401,
    name: "Neel Gosavi",
    role: "ADMIN",
    email: "neel@terna.edu",
    collegeId: "ADMIN01",
  },
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("cs_user");
      if (stored) setUser(JSON.parse(stored));
    } catch (e) {
      localStorage.removeItem("cs_user");
    }
    setLoading(false);
  }, []);

  // Real login (calls Spring Boot backend)
  const login = async (role, credentials) => {
    const { data } = await axiosClient.post(
      `/auth/login/${String(role).toLowerCase()}`,
      credentials
    );
    localStorage.setItem("cs_token", data.token);
    localStorage.setItem("cs_user", JSON.stringify(data.user));
    setUser(data.user);
    return data.user;
  };

  // Demo login (no backend needed — used by "Skip — Enter Demo Mode")
  const mockLogin = (role) => {
    const normalized = normalizeRole(role);
    const demoUser = demoUsers[normalized];

    localStorage.setItem("cs_token", "demo-token-" + normalized);
    localStorage.setItem("cs_user", JSON.stringify(demoUser));
    setUser(demoUser);

    return demoUser;
  };

  const logout = () => {
    localStorage.removeItem("cs_token");
    localStorage.removeItem("cs_user");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, mockLogin, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
};