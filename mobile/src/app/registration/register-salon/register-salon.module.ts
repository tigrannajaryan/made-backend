import { NgModule } from '@angular/core';
import { IonicPageModule } from 'ionic-angular';
import { RegisterSalonComponent } from './register-salon';

@NgModule({
  declarations: [
    RegisterSalonComponent
  ],
  imports: [
    IonicPageModule.forChild(RegisterSalonComponent)
  ]
})
export class RegisterSalonPageModule {}
