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
  defServices = [
    {
      id: 0,
      name: 'Black hair',
      color: 'black'
    },
    {
      id: 1,
      name: 'White hair',
      color: 'violet'
    }
  ];

  constructor(public navCtrl: NavController, public navParams: NavParams) {
  }
}
