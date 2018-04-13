import { NgModule } from '@angular/core';
import { IonicPageModule } from 'ionic-angular';
import { RegisterByEmailPage } from './register-by-email';

@NgModule({
  declarations: [
    RegisterByEmailPage,
  ],
  imports: [
    IonicPageModule.forChild(RegisterByEmailPage),
  ],
})
export class RegisterByEmailPageModule {}
