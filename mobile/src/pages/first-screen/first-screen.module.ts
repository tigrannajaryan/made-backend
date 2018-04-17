import { NgModule } from '@angular/core';
import { IonicPageModule } from 'ionic-angular';
import { FirstScreenPage } from './first-screen';

@NgModule({
  declarations: [
    FirstScreenPage,
  ],
  imports: [
    IonicPageModule.forChild(FirstScreenPage),
  ],
})
export class FirstScreenPageModule {}
