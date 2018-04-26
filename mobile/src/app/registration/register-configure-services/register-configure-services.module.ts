import { NgModule } from '@angular/core';
import { IonicPageModule } from 'ionic-angular';
import { SharedModule } from '../../../shared/shared.module';
import { RegisterConfigureServicesComponent } from './register-configure-services';

@NgModule({
  declarations: [
    RegisterConfigureServicesComponent
  ],
  imports: [
    IonicPageModule.forChild(RegisterConfigureServicesComponent),
    SharedModule
  ]
})
export class RegisterConfigureServicesPageModule {}
