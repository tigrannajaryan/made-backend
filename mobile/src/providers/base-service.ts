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
    console.log('BaseServiceProvider constructed.');
  }

  protected request<ResponseType>(method: string, apiPath: string, data: any = null): Promise<ResponseType> {
    // For help on how to use HttpClient see https://angular.io/guide/http

    const httpOptions = {
      headers: new HttpHeaders({
        // TODO: are standard HTTP headers defined as a constant anywhere?
        'Content-Type': 'application/json',
      }),
      body: data ? JSON.stringify(data) : null
    };

    const url = apiBaseUrl + apiPath;
    console.log("Calling API " + url);

    return this.http.request<ResponseType>(method, url, httpOptions).toPromise().
      catch(e => {
        console.log("API call failed: " + JSON.stringify(e));
        throw e;
      });
  }

  protected get<ResponseType>(apiPath: string): Promise<ResponseType> {
    return this.request("get", apiPath);
  }

  protected post<ResponseType>(apiPath: string, data: any): Promise<ResponseType> {
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
}
