import { Component } from '@angular/core';
import { IonicPage, NavController, NavParams } from 'ionic-angular';

/**
 * Generated class for the RegisterConfigureServicesPage page.
 *
 * See https://ionicframework.com/docs/components/#navigation for more info on
 * Ionic pages and navigation.
 */

@IonicPage()
@Component({
  selector: 'page-register-configure-services',
  templateUrl: 'register-configure-services.html'
})
export class RegisterConfigureServicesComponent {

  services = [
    { name: 'Haircut', price: 70 },
    { name: 'Nails', price: 30 }
  ];

  constructor(public navCtrl: NavController, public navParams: NavParams) {
  }
}
