import { create } from 'zustand'

import {
  login as apiLogin,
  register as apiRegister,
  verifyOTP as apiVerifyOTP,
  resendOTP as apiResendOTP,
} from '../lib/api'


// ============================================================
// TYPES
// ============================================================

export type UserRole =
  | 'GENERAL_USER'
  | 'LIBRARIAN'
  | 'ADMIN'


export interface User {

  id?: number

  user_id?: number

  name?: string

  full_name?: string

  email: string

  role: UserRole

  department?: string

  is_verified?: boolean

  [key: string]: any
}


interface AuthState {

  user: User | null

  token: string | null

  isAuthenticated: boolean

  loading: boolean

  error: string | null

  login: (
    email: string,
    password: string
  ) => Promise<any>

  register: (
    data: Record<string, any>
  ) => Promise<any>

  verifyOtp: (
    email: string,
    otp: string
  ) => Promise<any>

  resendOtp: (
    email: string
  ) => Promise<any>

  logout: () => void

  initialize: () => void

  clearError: () => void
}


// ============================================================
// STORE
// ============================================================

export const useAuthStore =
  create<AuthState>((set) => ({

    user:
      JSON.parse(
        localStorage.getItem(
          'luminar_user'
        ) || 'null'
      ),

    token:
      localStorage.getItem(
        'luminar_token'
      ),

    isAuthenticated:
      !!localStorage.getItem(
        'luminar_token'
      ),

    loading: false,

    error: null,


    // ========================================================
    // LOGIN
    // ========================================================

    login: async (
      email,
      password
    ) => {

      set({
        loading: true,
        error: null,
      })

      try {

        const response =
          await apiLogin(
            email,
            password
          )


        const token =
          response.access_token


        if (!token) {

          throw new Error(
            'Login succeeded but no access token was returned.'
          )
        }


        /*
         * The backend may return the user
         * directly in the login response.
         *
         * If it does not, we preserve the
         * existing user if one exists.
         */

        const user =
          response.user ||
          JSON.parse(
            localStorage.getItem(
              'luminar_user'
            ) || 'null'
          )


        localStorage.setItem(
          'luminar_token',
          token
        )


        if (user) {

          localStorage.setItem(
            'luminar_user',
            JSON.stringify(user)
          )
        }


        set({

          token,

          user,

          isAuthenticated: true,

          loading: false,

          error: null,

        })


        return response

      } catch (error: any) {

        const message =
          error?.message ||
          'Login failed.'


        set({

          loading: false,

          error: message,

        })


        throw error

      }
    },


    // ========================================================
    // REGISTER
    // ========================================================

    register: async (
      data
    ) => {

      set({

        loading: true,

        error: null,

      })


      try {

        const response =
          await apiRegister(
            data
          )


        set({

          loading: false,

          error: null,

        })


        return response

      } catch (error: any) {

        const message =
          error?.message ||
          'Registration failed.'


        set({

          loading: false,

          error: message,

        })


        throw error
      }
    },


    // ========================================================
    // VERIFY OTP
    // ========================================================

    verifyOtp: async (
      email,
      otp
    ) => {

      set({

        loading: true,

        error: null,

      })


      try {

        const response =
          await apiVerifyOTP(
            email,
            otp
          )


        set({

          loading: false,

          error: null,

        })


        return response

      } catch (error: any) {

        const message =
          error?.message ||
          'OTP verification failed.'


        set({

          loading: false,

          error: message,

        })


        throw error
      }
    },


    // ========================================================
    // RESEND OTP
    // ========================================================

    resendOtp: async (
      email
    ) => {

      set({

        loading: true,

        error: null,

      })


      try {

        const response =
          await apiResendOTP(
            email
          )


        set({

          loading: false,

          error: null,

        })


        return response

      } catch (error: any) {

        const message =
          error?.message ||
          'Could not resend OTP.'


        set({

          loading: false,

          error: message,

        })


        throw error
      }
    },


    // ========================================================
    // LOGOUT
    // ========================================================

    logout: () => {

      localStorage.removeItem(
        'luminar_token'
      )

      localStorage.removeItem(
        'luminar_user'
      )


      set({

        user: null,

        token: null,

        isAuthenticated: false,

        loading: false,

        error: null,

      })
    },


    // ========================================================
    // INITIALIZE
    // ========================================================

    initialize: () => {

      const token =
        localStorage.getItem(
          'luminar_token'
        )

      const user =
        JSON.parse(
          localStorage.getItem(
            'luminar_user'
          ) || 'null'
        )


      set({

        token,

        user,

        isAuthenticated: !!token,

      })
    },


    // ========================================================
    // CLEAR ERROR
    // ========================================================

    clearError: () => {

      set({
        error: null,
      })
    },

  }))