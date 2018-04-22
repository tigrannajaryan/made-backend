import { Component } from '@angular/core';
import { Validators, FormBuilder, FormGroup, FormControl } from '@angular/forms';
import { IonicPage, NavController, NavParams, AlertController } from 'ionic-angular';

import { PageNames } from '../../../pages/page-names';
import { StylistServiceProvider } from '../../../providers/stylist-service/stylist-service';

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

  form: FormGroup;

  constructor(
    public navCtrl: NavController,
    public navParams: NavParams,
    public formBuilder: FormBuilder,
    private apiService: StylistServiceProvider,
    private alertCtrl: AlertController) {

  }

  ionViewWillLoad() {
    this.form = this.formBuilder.group({
      first_name: new FormControl('', Validators.compose([
        Validators.maxLength(25),
        Validators.minLength(2),
        Validators.required
      ])),
      last_name: new FormControl('', Validators.compose([
        Validators.maxLength(25),
        Validators.minLength(2),
        Validators.required
      ])),
      phone: new FormControl('', Validators.compose([
        Validators.maxLength(15),
        Validators.minLength(5),
        Validators.required
      ])),
      salon_name: new FormControl('', Validators.compose([
        Validators.maxLength(25),
        Validators.minLength(3),
        Validators.nullValidator
      ])),
      salon_address: new FormControl('', Validators.required),
    });
  }

  async next() {
    try {
      // TODO: decide on fullname vs firstname/last and add phone field to the form.
      await this.apiService.setProfile({
        ...this.form.value
      });
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
