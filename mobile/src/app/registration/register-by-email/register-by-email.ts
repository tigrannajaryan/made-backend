import { Component } from '@angular/core';
import { IonicPage, NavController, NavParams, AlertController } from 'ionic-angular';
import { AuthServiceProvider } from '../../../providers/auth-service/auth-service';
import { PageNames } from '../../../pages/page-names';

/**
 * Generated class for the RegisterByEmailPage page.
 *
 * See https://ionicframework.com/docs/components/#navigation for more info on
 * Ionic pages and navigation.
 */

@IonicPage()
@Component({
  selector: 'page-register-by-email',
  templateUrl: 'register-by-email.html',
})
export class RegisterByEmailPage {

  formData = { email: "", password: "" };

  constructor(
    public navCtrl: NavController,
    public navParams: NavParams,
    private authService: AuthServiceProvider,
    private alertCtrl: AlertController) {
  }

  ionViewDidLoad() {
    console.log('ionViewDidLoad RegisterByEmailPage');
  }

  async register() {
    try {
      await this.authService.registerByEmail(this.formData);
      this.navCtrl.push(PageNames.RegisterSalon, {}, { animate: false });
    }
    catch (e) {
      const alert = this.alertCtrl.create({
        title: 'Registration failed',
        subTitle: e.message,
        buttons: ['Dismiss']
      });
      alert.present();
    }
  }
}
