import { Component } from '@angular/core';
import { IonicPage, NavController, NavParams } from 'ionic-angular';
import { PageNames } from '../page-names';

/**
 * Generated class for the FirstScreenPage page.
 *
 * See https://ionicframework.com/docs/components/#navigation for more info on
 * Ionic pages and navigation.
 */

@IonicPage()
@Component({
  selector: 'page-first-screen',
  templateUrl: 'first-screen.html'
})
export class FirstScreenComponent {

  constructor(public navCtrl: NavController, public navParams: NavParams) {
  }

  loginByEmail(): void {
    this.navCtrl.push(PageNames.Login, {}, {animate: false});
  }

  register(): void {
    this.navCtrl.push(PageNames.RegisterByEmail, {}, {animate: false});
  }
}
