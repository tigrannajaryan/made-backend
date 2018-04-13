import { NgModule } from '@angular/core';
import { IonicPageModule } from 'ionic-angular';
import { RegisterSalonPage } from './register-salon';

@NgModule({
  declarations: [
    RegisterSalonPage,
  ],
  imports: [
    IonicPageModule.forChild(RegisterSalonPage),
  ],
})
export class RegisterSalonPageModule {}
