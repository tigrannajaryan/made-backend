import { NgModule } from '@angular/core';
import { IonicModule } from 'ionic-angular';
import { ComponentsModule } from '../components/components.module';
import { BaseServiceProvider } from '../providers/base-service';

const ex = [
  ComponentsModule
];

@NgModule({
  imports: [
    IonicModule,
    ...ex
  ],
  exports: [
    ...ex
  ],
  providers: [
    BaseServiceProvider
  ]
})
export class SharedModule {}
