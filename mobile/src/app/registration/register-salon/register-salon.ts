import { Component } from '@angular/core';
import { IonicPage, NavController, NavParams, AlertController } from 'ionic-angular';
import { PageNames } from '../../../pages/page-names';
import { StylistServiceProvider } from '../../../providers/stylist-service/stylist-service';
import { StylistProfile } from '../../../providers/stylist-service/stylist-models';

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

  formData: StylistProfile = {
    first_name: "",
    last_name: "",
    phone: "",
    salon_name: "",
    salon_address: ""
  }

  constructor(
    public navCtrl: NavController,
    public navParams: NavParams,
    private apiService: StylistServiceProvider,
    private alertCtrl: AlertController) {
  }

  async ionViewDidLoad() {
    try {
      console.log('ionViewDidLoad ' + PageNames.RegisterSalon);
      this.formData = await this.apiService.getProfile();
    } catch (e) {
      console.error(e);
    }
  }

  async next() {
    try {
      await this.apiService.setProfile(this.formData);
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
