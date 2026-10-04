import { create } from "zustand";
import { useLibraryStore } from "./useLibraryStore";

import {
  login as apiLogin,
  staffLogin as apiStaffLogin,
  register as apiRegister,
  verifyOTP as apiVerifyOTP,
  resendOTP as apiResendOTP,
} from "../lib/api";

// ============================================================
// TYPES
// ============================================================

export type UserRole = "GENERAL_USER" | "LIBRARIAN" | "ADMIN";

export interface User {
  id?: number;

  user_id?: number;

  name?: string;

  full_name?: string;

  email: string;

  role: UserRole;

  department?: string;

  is_verified?: boolean;

  [key: string]: any;
}

interface AuthState {
  user: User | null;

  token: string | null;

  isAuthenticated: boolean;

  loading: boolean;

  error: string | null;

  login: (email: string, password: string, staff?: boolean) => Promise<any>;
  loginStaff: (email: string, password: string) => Promise<any>;

  register: (data: Record<string, any>) => Promise<any>;

  verifyOtp: (email: string, otp: string) => Promise<any>;

  resendOtp: (email: string) => Promise<any>;

  logout: () => void;

  initialize: () => void;

  clearError: () => void;
}

// ============================================================
// STORE
// ============================================================

function readStoredUser(): User | null {
  try {
    const user = JSON.parse(localStorage.getItem("luminar_user") || "null");
    if (!localStorage.getItem("luminar_token") || !user || typeof user.email !== "string" || !["GENERAL_USER", "LIBRARIAN", "ADMIN"].includes(user.role)) throw new Error("Invalid stored session");
    return user;
  } catch {
    localStorage.removeItem("luminar_user");
    localStorage.removeItem("luminar_token");
    return null;
  }
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: readStoredUser(),

  token: localStorage.getItem("luminar_token"),

  isAuthenticated: !!localStorage.getItem("luminar_token"),

  loading: false,

  error: null,

  // ========================================================
  // LOGIN
  // ========================================================

  loginStaff: (email, password) => get().login(email, password, true),

  login: async (email, password, staff = false) => {
    set({
      loading: true,
      error: null,
    });

    try {
      const response = await (staff ? apiStaffLogin : apiLogin)(email.trim(), password);

      const token = response.access_token;

      if (!token) {
        throw new Error("Login succeeded but no access token was returned.");
      }

      // Trust the user returned for this login, never a previous session.

      const user = response.user;

      if (!user || !["GENERAL_USER", "LIBRARIAN", "ADMIN"].includes(user.role))
        throw new Error("Login did not return a supported user role.");
      if (staff && !['ADMIN', 'LIBRARIAN'].includes(user.role))
        throw new Error('This account is not authorized for staff access.');

      useLibraryStore.getState().clearUserData();
      localStorage.setItem("luminar_token", token);

      if (user) {
        localStorage.setItem("luminar_user", JSON.stringify(user));
      }

      set({
        token,

        user,

        isAuthenticated: true,

        loading: false,

        error: null,
      });

      return response;
    } catch (error: any) {
      const message = error?.message || "Login failed.";

      set({
        loading: false,

        error: message,
      });

      throw error;
    }
  },

  // ========================================================
  // REGISTER
  // ========================================================

  register: async (data) => {
    set({
      loading: true,

      error: null,
    });

    try {
      const response = await apiRegister(data);

      set({
        loading: false,

        error: null,
      });

      return response;
    } catch (error: any) {
      const message = error?.message || "Registration failed.";

      set({
        loading: false,

        error: message,
      });

      throw error;
    }
  },

  // ========================================================
  // VERIFY OTP
  // ========================================================

  verifyOtp: async (email, otp) => {
    set({
      loading: true,

      error: null,
    });

    try {
      const response = await apiVerifyOTP(email, otp);

      set({
        loading: false,

        error: null,
      });

      return response;
    } catch (error: any) {
      const message = error?.message || "OTP verification failed.";

      set({
        loading: false,

        error: message,
      });

      throw error;
    }
  },

  // ========================================================
  // RESEND OTP
  // ========================================================

  resendOtp: async (email) => {
    set({
      loading: true,

      error: null,
    });

    try {
      const response = await apiResendOTP(email);

      set({
        loading: false,

        error: null,
      });

      return response;
    } catch (error: any) {
      const message = error?.message || "Could not resend OTP.";

      set({
        loading: false,

        error: message,
      });

      throw error;
    }
  },

  // ========================================================
  // LOGOUT
  // ========================================================

  logout: () => {
    useLibraryStore.getState().clearUserData();
    localStorage.removeItem("luminar_token");

    localStorage.removeItem("luminar_user");

    set({
      user: null,

      token: null,

      isAuthenticated: false,

      loading: false,

      error: null,
    });
  },

  // ========================================================
  // INITIALIZE
  // ========================================================

  initialize: () => {
    const user = readStoredUser();
    const token = localStorage.getItem("luminar_token");

    set({
      token,

      user,

      isAuthenticated: !!token && !!user,
    });
  },

  // ========================================================
  // CLEAR ERROR
  // ========================================================

  clearError: () => {
    set({
      error: null,
    });
  },
}));
