import { Component } from '@angular/core';
import { IonicPage, NavController, NavParams, AlertController } from 'ionic-angular';
import { AuthServiceProvider } from '../../../providers/auth-service/auth-service';
import { PageNames } from '../../../pages/page-names';

/**
 * Generated class for the RegisterSalonPage page.
 *
 * See https://ionicframework.com/docs/components/#navigation for more info on
 * Ionic pages and navigation.
 */

@IonicPage()
@Component({
  selector: 'page-register-salon',
  templateUrl: 'register-salon.html',
})
export class RegisterSalonPage {

  formData = {
    first_name: "",
    last_name: "",
    phone: "",
    salon_name: "",
    salon_address: ""
  }

  constructor(
    public navCtrl: NavController,
    public navParams: NavParams,
    private authService: AuthServiceProvider,
    private alertCtrl: AlertController) {
  }

  ionViewDidLoad() {
    console.log('ionViewDidLoad '+PageNames.RegisterSalon);
  }

  async next() {
    try {
      await this.authService.setStylistProfile(this.formData);
      this.navCtrl.push(PageNames.RegisterConfigureServices, {}, { animate: false });
    }
    catch (e) {
      const alert = this.alertCtrl.create({
        title: 'Saving profile information failed',
        subTitle: e.message,
        buttons: ['Dismiss']
      });
      alert.present();
    }
  }
}
