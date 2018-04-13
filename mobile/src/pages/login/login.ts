import { Component } from '@angular/core';
import { IonicPage, NavController, NavParams, AlertController } from 'ionic-angular';
import { AuthServiceProvider } from '../../providers/auth-service/auth-service';

/**
 * Generated class for the LoginPage page.
 *
 * See https://ionicframework.com/docs/components/#navigation for more info on
 * Ionic pages and navigation.
 */

@IonicPage()
@Component({
  selector: 'page-login',
  templateUrl: 'login.html',
})
export class LoginPage {

  userData = { email: "", password: "" };

  constructor(public navCtrl: NavController,
    public navParams: NavParams,
    public authService: AuthServiceProvider,
    private alertCtrl: AlertController) {
  }

  ionViewDidLoad() {
    console.log('ionViewDidLoad LoginPage');
  }

  login() {
    this.authService.doAuth(this.userData).
      then((authResponse) => {
        // Auth successfull. Remember token in local storage.
        console.log("Auth API successfull, token=" + authResponse.token);
        localStorage.setItem('authToken', JSON.stringify(authResponse.token));

        // Erase all previous navigation history and make HomePage the root
        this.navCtrl.setRoot('RegisterSalonPage');
      },
        (err) => {
          // Error log
          console.log("Login failed:" + JSON.stringify(err));

          // Show an error message
          let alert = this.alertCtrl.create({
            title: 'Login failed',
            subTitle: 'Invalid email or password',
            buttons: ['Dismiss']
          });
          alert.present();
        });

  }
}
