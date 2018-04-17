import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import 'rxjs/add/operator/toPromise';

// TODO: the URL should be different for development, staging and production
const apiBaseUrl = 'http://betterbeauty.local:8000/api/v1/';

export interface AuthCredentials {
  email: string;
  password: string;
}

export interface AuthResponse {
  token: string;
}

export interface RegisterError {
  error: { email: string, password: string };
}

export interface StylistProfile {
  first_name: string;
  last_name: string;
  phone: string;
  salon_name: string;
  salon_address: string;
}

/**
 * AuthServiceProvider provides authentication against server API.
 */
@Injectable()
export class AuthServiceProvider {

  private authResponse: AuthResponse;

  constructor(public http: HttpClient) {
    console.log('AuthServiceProvider constructed.');
  }

  private post<ResponseType>(apiPath: string, data: any): Promise<ResponseType> {
    // For help on how to use HttpClient see https://angular.io/guide/http

    const httpOptions = {
      headers: new HttpHeaders({
        // TODO: are standard HTTP headers defined as a constant anywhere?
        'Content-Type': 'application/json',
      })
    };

    const url = apiBaseUrl + apiPath;
    console.log("Calling API " + url);

    return this.http.post<ResponseType>(url, JSON.stringify(data), httpOptions).toPromise().
      catch(e => {
        console.log("API call failed: " + JSON.stringify(e));
        throw e;
      });
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
      catch(e => {
        // Failed authentication. Clear previously saved successfull response (if any).
        this.authResponse = null;
        throw e;
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

  /**
   * Set the profile of the stylist. The stylist must be already authenticated as a user.
   * Existing limitation: does not work if the stylist profile already exists,
   * so this is a works-only-once type of call. I asked backend to change the behavior.
   */
  async setStylistProfile(data: StylistProfile): Promise<AuthResponse> {
    return this.post<AuthResponse>('stylist/profile', data);
  }
}
