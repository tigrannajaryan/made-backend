import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import 'rxjs/add/operator/toPromise';
import { BaseServiceProvider } from '../base-service';

export interface AuthCredentials {
  email: string;
  password: string;
}

export interface AuthResponse {
  token: string;
}

export interface AuthError {
  non_field_errors?: string[];
  email?: string[]
  password?: string[];
}

/**
 * AuthServiceProvider provides authentication against server API.
 */
@Injectable()
export class AuthServiceProvider extends BaseServiceProvider {

  private authResponse: AuthResponse;

  constructor(public http: HttpClient) {
    super(http);
    console.log('AuthServiceProvider constructed.');
  }

  /**
   * Process a response to authentication API call. If the response is successfull
   * remember it. If the call failed clear previously rememebered response.
   * @param apiCall function to call to perform the API call. Must return a promise
   *                to AuthResponse.
   * @returns the same response that it received from apiCall (or re-throws the error).
   */
  private async processAuthResponse(apiCall: () => Promise<AuthResponse>): Promise<AuthResponse> {
    return apiCall().
      then(response => {
        // Save auth response
        this.authResponse = response;
        return response;
      }).
      catch((e: HttpErrorResponse) => {
        // Failed authentication. Clear previously saved successfull response (if any).
        this.authResponse = null;

        if (e.error instanceof Error) {
          throw e.error;
        }

        const err = e.error as AuthError;
        throw err;
      });
  }

  /**
   * Authenticate using the API. If successfull remembers the auth response
   * and token which can be later obtained via getAuthToken().
   */
  async doAuth(credentials: AuthCredentials): Promise<AuthResponse> {
    return this.processAuthResponse(
      () => { return this.post<AuthResponse>('auth/get-token', credentials) });
  }

  /**
   * Register a new user authenticate using the API. If successfull remembers the auth response
   * and token which can be later obtained via getAuthToken().
   */
  async registerByEmail(credentials: AuthCredentials): Promise<AuthResponse> {
    return this.processAuthResponse(
      () => { return this.post<AuthResponse>('auth/register', credentials) });
  }

  /**
   * Return token remembered after the last succesfull authentication.
   */
  getAuthToken(): string {
    return this.authResponse ? this.authResponse.token : null;
  }
}
