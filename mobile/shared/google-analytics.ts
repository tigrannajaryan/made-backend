import { Injectable } from '@angular/core';
import { GoogleAnalytics } from '@ionic-native/google-analytics';

/**
 * Wrapper class for Google Analytics which initializes it
 * and can defer calls until the initializtion is ready or
 * skip calls if initialization fails.
 */
@Injectable()
export class GAWrapper {
  private ready = false;
  private failed = false;

  constructor(
    private ga: GoogleAnalytics
  ) {
  }

  async init(id: string): Promise<void> {

    try {
      await this.ga.startTrackerWithId(id);
      this.ready = true;
    } catch (e) {
      this.failed = true;
      throw e;
    }
  }

  setUserId(userId: string): void {
    this.execWhenReady(() => this.ga.setUserId(userId));
  }

  trackView(title: string, campaignUrl?: string, newSession?: boolean): void {
    this.execWhenReady(() => this.ga.trackView(title, campaignUrl, newSession));
  }

  trackTiming(category: string, intervalInMilliseconds: number, variable: string, label: string): void {
    this.execWhenReady(() => this.ga.trackTiming(category, intervalInMilliseconds, variable, label));
  }

  protected execWhenReady(func: Function): void {
    if (this.ready) {
      func();
    } else {
      const retryIntervalMsec = 500;
      const timer = setInterval(() => {
        if (this.ready) {
          func();
        } else if (!this.failed) {
          return;
        }
        clearInterval(timer);
      }, retryIntervalMsec);
    }
  }
}
