import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import 'rxjs/add/operator/toPromise';

// TODO: the URL should be different for development, staging and production
const apiBaseUrl = 'http://192.168.31.109:8000/api/v1/';

/**
 * AuthServiceProvider provides authentication against server API.
 */
@Injectable()
export class BaseServiceProvider {

  constructor(public http: HttpClient) {
  }

  protected request<ResponseType>(method: string, apiPath: string, data?: any): Promise<ResponseType> {
    // For help on how to use HttpClient see https://angular.io/guide/http

    const httpOptions = {
      headers: new HttpHeaders({
        // TODO: are standard HTTP headers defined as a constant anywhere?
        'Content-Type': 'application/json'
      }),
      body: data ? JSON.stringify(data) : undefined
    };

    const url = apiBaseUrl + apiPath;

    return this.http.request<ResponseType>(method, url, httpOptions)
      .toPromise()
      .catch(e => {
        throw e;
      });
  }

  protected get<ResponseType>(apiPath: string): Promise<ResponseType> {
    return this.request('get', apiPath);
  }

  protected post<ResponseType>(apiPath: string, data: any): Promise<ResponseType> {
    // For help on how to use HttpClient see https://angular.io/guide/http

    const httpOptions = {
      headers: new HttpHeaders({
        // TODO: are standard HTTP headers defined as a constant anywhere?
        'Content-Type': 'application/json'
      })
    };

    const url = apiBaseUrl + apiPath;

    return this.http.post<ResponseType>(url, JSON.stringify(data), httpOptions)
      .toPromise()
      .catch(e => {
        throw e;
      });
  }
}
