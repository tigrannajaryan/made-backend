import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BaseServiceProvider } from '../base-service';
import { StylistProfile } from './stylist-models';

const profileAPIPath = 'stylist/profile';

/**
 * StylistServiceProvider provides authentication against server API.
 * The service requires the current user to be authenticated using
 * AuthServiceProvider.
 */
@Injectable()
export class StylistServiceProvider extends BaseServiceProvider {

  constructor(public http: HttpClient) {
    super(http);
  }

  /**
   * Set the profile of the stylist. The stylist must be already authenticated as a user.
   */
  async setProfile(data: StylistProfile): Promise<StylistProfile> {
    return this.post<StylistProfile>(profileAPIPath, data);
  }

  /**
   * Get the profile of the stylist. The stylist must be already authenticated as a user.
   */
  async getProfile(): Promise<StylistProfile> {
    return this.get<StylistProfile>(profileAPIPath);
  }
}
